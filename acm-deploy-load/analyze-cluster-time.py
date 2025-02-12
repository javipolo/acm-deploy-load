#!/usr/bin/env python3
#
# Analyze a single Cluster's provision and du profile time
#
#  Copyright 2023 Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import argparse
from collections import OrderedDict
from datetime import datetime
from datetime import timedelta
import json
from utils.command import command
from utils.output import log_write
import logging
from pathlib import Path
import requests
import sys
import time


logging.basicConfig(level=logging.INFO, format="%(asctime)s : %(levelname)s : %(threadName)s : %(message)s")
logger = logging.getLogger("acm-deploy-load")
logging.Formatter.converter = time.gmtime


# TODO:
# * Get Policy timings
# * Get BMH timings?

def main():
  start_time = time.time()

  parser = argparse.ArgumentParser(
      description="Analyze a single Cluster's deploy and du profile time",
      prog="analyze-cluster-time.py", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument("-c", "--cluster", type=str, default="e38-h06-000-r650",
                      help="The name of the cluster should match namespace")
  parser.add_argument("results_directory", type=str, help="The location to place analyzed data")
  cliargs = parser.parse_args()

  logger.info("Analyze cluster time")
  ts = datetime.now().strftime("%Y%m%d-%H%M%S")

  report_data = OrderedDict()
  report_data["aci_created"] = {"ts": "", "duration": 0, "total_duration": 0}
  report_data["aci_validations_passing"] = {"ts": "", "duration": 0, "total_duration": 0}
  report_data["aci_cluster_installing"] = {"ts": "", "duration": 0, "total_duration": 0}
  report_data["aci_cluster_finalized"] = {"ts": "", "duration": 0, "total_duration": 0}
  report_data["aci_cluster_installed"] = {"ts": "", "duration": 0, "total_duration": 0}
  report_data["aci_completed"] = {"ts": "", "duration": 0, "total_duration": 0}

  report_data["mc_imported"] = {"ts": "", "duration": 0, "total_duration": 0}
  report_data["mc_joined"] = {"ts": "", "duration": 0, "total_duration": 0}

  report_data["cgu_created"] = {"ts": "", "duration": 0, "total_duration": 0}
  report_data["cgu_started"] = {"ts": "", "duration": 0, "total_duration": 0}
  report_data["cgu_completed"] = {"ts": "", "duration": 0, "total_duration": 0}

  # Create results directory and save raw data
  raw_data_dir = "{}/cluster-time-{}".format(cliargs.results_directory, cliargs.cluster)
  Path(raw_data_dir).mkdir(parents=True, exist_ok=True)
  logger.info("Storing results in: {}".format(raw_data_dir))
  report_stats_file = "{}/cluster-time-{}.stats".format(cliargs.results_directory, cliargs.cluster)

  # Get ACI data
  oc_cmd = ["oc", "get", "agentclusterinstalls", "-n", cliargs.cluster, cliargs.cluster, "-o", "json"]
  rc, output = command(oc_cmd, False, retries=3, no_log=True)
  if rc != 0:
    logger.error("analyze-cluster-time, oc get agentclusterinstalls rc: {}".format(rc))
    sys.exit(1)
  with open("{}/aci.json".format(raw_data_dir), "w") as data_file:
    data_file.write(output)
  aci_data = json.loads(output)

  # Get ACI events url
  aci_eventsurl = aci_data["status"]["debugInfo"]["eventsURL"]
  logger.info("Getting ACI Events Data: {}".format(aci_eventsurl))
  response = requests.get(aci_eventsurl, verify=False)
  aci_event_data = response.json()
  with open("{}/aci_events.json".format(raw_data_dir), "w") as data_file:
    data_file.write(str(response.json()))

  # Get managedcluster data
  oc_cmd = ["oc", "get", "managedcluster", cliargs.cluster, "-o", "json"]
  rc, output = command(oc_cmd, False, retries=3, no_log=True)
  if rc != 0:
    logger.error("analyze-cluster-time, oc get managedcluster rc: {}".format(rc))
    sys.exit(1)
  with open("{}/mc.json".format(raw_data_dir), "w") as data_file:
    data_file.write(output)
  mc_data = json.loads(output)

  # Get CGU data
  oc_cmd = ["oc", "get", "clustergroupupgrades", "-n", "ztp-install", cliargs.cluster, "-o", "json"]
  rc, output = command(oc_cmd, False, retries=3, no_log=True)
  if rc != 0:
    logger.error("analyze-cluster-time, oc get clustergroupupgrades rc: {}".format(rc))
    sys.exit(1)
  with open("{}/cgu.json".format(raw_data_dir), "w") as data_file:
    data_file.write(output)
  cgu_data = json.loads(output)

  # Get policy data
  oc_cmd = ["oc", "get", "policies", "-n", cliargs.cluster, "-o", "json"]
  rc, output = command(oc_cmd, False, retries=3, no_log=True)
  if rc != 0:
    logger.error("analyze-cluster-time, oc get policies rc: {}".format(rc))
    sys.exit(1)
  with open("{}/policies.json".format(raw_data_dir), "w") as data_file:
    data_file.write(output)
  policy_data = json.loads(output)


  # Process ACI Data
  report_data["aci_created"]["ts"] = datetime.strptime(aci_data["metadata"]["creationTimestamp"], "%Y-%m-%dT%H:%M:%SZ")
  for condition in aci_data["status"]["conditions"]:
    cond_lpt = condition["lastProbeTime"]
    cond_ltt = condition["lastTransitionTime"]
    cond_message = condition["message"]
    cond_reason = condition["reason"]
    cond_status = condition["status"]
    cond_type = condition["type"]
    # logger.info("ACI status: {}, type: {}, reason: {}, ltt: {}, lpt: {}".format(cond_type, cond_reason, cond_status, cond_ltt, cond_lpt))
    if cond_type == "Validated" and cond_reason == "ValidationsPassing":
      report_data["aci_validations_passing"]["ts"] = datetime.strptime(cond_lpt, "%Y-%m-%dT%H:%M:%SZ")
    if cond_type == "Completed" and cond_reason == "InstallationCompleted":
      report_data["aci_completed"]["ts"] = datetime.strptime(cond_lpt, "%Y-%m-%dT%H:%M:%SZ")


  # Process aci event data
  last_ts = ""
  for event in aci_event_data:
    event_time = datetime.strptime(event["event_time"], "%Y-%m-%dT%H:%M:%S.%fZ")
    if event["message"].lower() == "updated status of the cluster to installing":
      # logger.info("ACI Event detected: Cluster installing - {}".format(event_time.strftime("%Y-%m-%dT%H:%M:%SZ")))
      report_data["aci_cluster_installing"]["ts"] = event_time
    elif event["message"].lower() == "updated status of the cluster to finalizing":
      # logger.info("ACI Event detected: Cluster finalizing - {}".format(event_time.strftime("%Y-%m-%dT%H:%M:%SZ")))
      report_data["aci_cluster_finalized"]["ts"] = event_time
    if "operator cvo status: available message: done applying" in event["message"].lower():
      # logger.info("ACI Event detected: Cluster installed - {}".format(event_time.strftime("%Y-%m-%dT%H:%M:%SZ")))
      report_data["aci_cluster_installed"]["ts"] = event_time


  # mc_creation_timestamp = mc_data["metadata"]["creationTimestamp"]
  for condition in mc_data["status"]["conditions"]:
    cond_ltt = condition["lastTransitionTime"]
    cond_message = condition["message"]
    cond_reason = condition["reason"]
    cond_status = condition["status"]
    cond_type = condition["type"]
    # logger.info("MC status: {}, type: {}, reason: {}, ltt: {}".format(cond_type, cond_status, cond_reason, cond_ltt))
    if cond_type == "ManagedClusterJoined" and cond_reason == "ManagedClusterJoined":
      report_data["mc_joined"]["ts"] = datetime.strptime(cond_ltt, "%Y-%m-%dT%H:%M:%SZ")
    if cond_type == "ManagedClusterImportSucceeded" and cond_reason == "ManagedClusterImported":
      report_data["mc_imported"]["ts"] = datetime.strptime(cond_ltt, "%Y-%m-%dT%H:%M:%SZ")


  # Process CGU Data
  report_data["cgu_created"]["ts"] = datetime.strptime(cgu_data["metadata"]["creationTimestamp"], "%Y-%m-%dT%H:%M:%SZ")
  report_data["cgu_started"]["ts"] = datetime.strptime(cgu_data["status"]["status"]["startedAt"], "%Y-%m-%dT%H:%M:%SZ")
  report_data["cgu_completed"]["ts"] = datetime.strptime(cgu_data["status"]["status"]["completedAt"], "%Y-%m-%dT%H:%M:%SZ")
  cgu_duration = 0


  # Calculate durations between steps
  last_ts = ""
  total_duration = 0
  for step in report_data:
    if last_ts == "":
      duration = 0
    else:
      duration = round((report_data[step]["ts"] - last_ts).total_seconds())
      total_duration += duration
    report_data[step]["duration"] = duration
    report_data[step]["total_duration"] = total_duration
    last_ts = report_data[step]["ts"]

  aci_total_duration = (report_data["aci_completed"]["ts"] - report_data["aci_created"]["ts"]).total_seconds()
  mc_gap_duration = (report_data["cgu_created"]["ts"] - report_data["aci_completed"]["ts"]).total_seconds()
  cgu_total_duration = (report_data["cgu_completed"]["ts"] - report_data["cgu_created"]["ts"]).total_seconds()
  cluster_total_duration = (report_data["cgu_completed"]["ts"] - report_data["aci_created"]["ts"]).total_seconds()

  # Output the report on the cluster
  logger.info("################################################################################")

  with open(report_stats_file, "w") as stats_file:
    log_write(stats_file, "Install times on {}".format(cliargs.cluster))

    log_write(stats_file, "{:25} {:20} {:8} {:5}".format("Step", "Timestamp", "Duration", "Total"))
    for step in report_data:
      log_write(stats_file, "{:25} {:20} {:8} {:5}".format(step, report_data[step]["ts"].strftime("%Y-%m-%dT%H:%M:%SZ"), report_data[step]["duration"], report_data[step]["total_duration"]))

    log_write(stats_file, "################################################################################")

    log_write(stats_file, "Major phases of install for {}".format(cliargs.cluster))
    log_write(stats_file, "ACI Total:         {:8} :: {}".format(aci_total_duration, str(timedelta(seconds=aci_total_duration))))
    log_write(stats_file, "MC Gap Total:      {:8} :: {}".format(mc_gap_duration, str(timedelta(seconds=mc_gap_duration))))
    log_write(stats_file, "CGU Total:         {:8} :: {}".format(cgu_total_duration, str(timedelta(seconds=cgu_total_duration))))
    log_write(stats_file, "Cluster Total:     {:8} :: {}".format(cluster_total_duration, str(timedelta(seconds=cluster_total_duration))))


  logger.info("################################################################################")

  end_time = time.time()
  logger.info("Took {}s".format(round(end_time - start_time, 1)))

if __name__ == "__main__":
  sys.exit(main())
