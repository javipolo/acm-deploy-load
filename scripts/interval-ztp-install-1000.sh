#!/usr/bin/env bash
# Test limited to 1000 clusters
set -e
set -o pipefail

iteration=1
interval_period=3600
batch=500
clusters_per_app=100

wan_em="(None)"
# wan_em="(50ms/0.02)"
# wan_em="(50ms/0.02) / 100Mbps"
# wan_em="(50ms/0.02) / 20Mbps"

ts="$(date -u +%Y%m%d-%H%M%S)"
log_file="iz-1000-${ts}.log"
acm_ver=$(cat /root/rhacm-deploy/deploy/snapshot.ver)
test_ver="ZTP Scale Run ${iteration}"
hub_ocp=$(oc version -o json | jq -r '.openshiftVersion')
# grep will cause error code 141 since it prints only the first match
cluster_ocp=$(cat /root/hv-vm/*/siteconfigs/*-siteconfig.yml | grep "clusterImageSetNameRef:" -m 1 | awk '{print $NF}' | sed 's/openshift-//' || if [[ $? -eq 141 ]]; then true; else exit $?; fi)

time ./acm-deploy-load/acm-deploy-load.py --acm-version "${acm_ver}" --test-version "${test_ver}" --hub-version "${hub_ocp}" --deploy-version "${cluster_ocp}" --wan-emulation "${wan_em}" -e 1000 --clusters-per-app ${clusters_per_app} -w -i 60 -t int-ztp-${clusters_per_app}-${batch}b-${interval_period}i-${iteration} interval -b ${batch} -i ${interval_period} ztp 2>&1 | tee ${log_file}

results_dir=$(grep "Results data captured in:" $log_file | awk '{print $NF}')

echo "################################################################################" 2>&1 | tee -a ${log_file}

time ./acm-deploy-load/graph-acm-deploy.py --acm-version "${acm_ver}" --test-version "${test_ver}" --hub-version "${hub_ocp}" --deploy-version "${cluster_ocp}" --wan-emulation "${wan_em}" ${results_dir} 2>&1 | tee -a ${log_file}

echo "################################################################################" 2>&1 | tee -a ${log_file}

time ./acm-deploy-load/analyze-acm-deploy-time.py ${results_dir} 2>&1 | tee -a ${log_file}

echo "################################################################################" 2>&1 | tee -a ${log_file}

time ./scripts/post-ztp-install-data-collection.sh -k 2>&1 | tee -a ${log_file}

echo "################################################################################" 2>&1 | tee -a ${log_file}

time ./acm-deploy-load/analyze-agentclusterinstalls.py ${results_dir} 2>&1 | tee -a ${log_file}

echo "################################################################################" 2>&1 | tee -a ${log_file}

time ./acm-deploy-load/analyze-clustergroupupgrades.py ${results_dir} 2>&1 | tee -a ${log_file}

echo "################################################################################" 2>&1 | tee -a ${log_file}

oc adm must-gather --dest-dir="${results_dir}/must-gather-${ts}" 2>&1 | tee -a ${log_file}
tar caf ${results_dir}/must-gather-${ts}.tar.gz --remove-files ${results_dir}/must-gather-${ts} 2>&1 | tee -a ${log_file}

echo "################################################################################" 2>&1 | tee -a ${log_file}

start_time=$(grep "Start Time:" ${results_dir}/report.txt | awk '{print $4}')
end_time=$(grep "End Time:" ${results_dir}/report.txt | awk '{print $4}')
time ./acm-deploy-load/analyze-prometheus.py -p "deploy-pa" -s "${start_time}" -e "${end_time}" ${results_dir} 2>&1 | tee -a ${log_file}
echo "time ./acm-deploy-load/analyze-prometheus.py -p deploy-pa -s ${start_time} -e ${end_time} ${results_dir}" | tee -a ${log_file}

echo "################################################################################" 2>&1 | tee -a ${log_file}

meta=$(kubectl promdump meta -n openshift-monitoring -p prometheus-k8s-0 -c prometheus -d /prometheus </dev/null 2>&1 | tee -a ${log_file})
kubectl promdump -n openshift-monitoring -p prometheus-k8s-0 -c prometheus -d /prometheus --min-time "$(echo $meta | cut -d \| -f 5 | cut -d \  -f 2,3)" --max-time "$(echo $meta | cut -d \| -f 6 | cut -d \  -f 2,3)" > ${results_dir}/promdump-${ts}.tar.gz

echo "################################################################################" 2>&1 | tee -a ${log_file}

echo "Finished" 2>&1 | tee -a ${log_file}

cat ${log_file} | grep -v WARNING > ${results_dir}/${log_file}.nowarn

mv ${log_file} ${results_dir}

gzip ${results_dir}/${log_file}
