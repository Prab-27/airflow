#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

from abc import ABC
from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING

from airflow.configuration import conf
from airflow.exceptions import AirflowClusterPolicySkipDag, AirflowClusterPolicyViolation
from airflow.sdk import BaseOperator

if TYPE_CHECKING:
    from airflow.models.dag import DAG
    from airflow.models.taskinstance import TaskInstance


# [START example_cluster_policy_rule]
def task_must_have_owners(task: BaseOperator):
    if task.owner and not isinstance(task.owner, str):
        raise AirflowClusterPolicyViolation(f"""owner should be a string. Current value: {task.owner!r}""")

    if not task.owner or task.owner.lower() == conf.get("operators", "default_owner"):
        raise AirflowClusterPolicyViolation(
            f"""Task must have non-None non-default owner. Current value: {task.owner}"""
        )


# [END example_cluster_policy_rule]


# [START example_list_of_cluster_policy_rules]
TASK_RULES: list[Callable[[BaseOperator], None]] = [
    task_must_have_owners,
]


def _check_task_rules(current_task: BaseOperator):
    """Check task rules for given task."""
    notices = []
    for rule in TASK_RULES:
        try:
            rule(current_task)
        except AirflowClusterPolicyViolation as ex:
            notices.append(str(ex))
    if notices:
        notices_list = " * " + "\n * ".join(notices)
        raise AirflowClusterPolicyViolation(
            f"DAG policy violation (DAG ID: {current_task.dag_id}, Path: {current_task.dag.fileloc}):\n"
            f"Notices:\n"
            f"{notices_list}"
        )


def example_task_policy(task: BaseOperator):
    """Ensure Tasks have non-default owners."""
    _check_task_rules(task)


# [END example_list_of_cluster_policy_rules]


# [START example_dag_cluster_policy]
def dag_policy(dag: DAG):
    """Ensure that DAG has at least one tag and skip the DAG with `only_for_beta` tag."""
    if not dag.tags:
        raise AirflowClusterPolicyViolation(
            f"DAG {dag.dag_id} has no tags. At least one tag required. File path: {dag.fileloc}"
        )

    if "only_for_beta" in dag.tags:
        raise AirflowClusterPolicySkipDag(
            f"DAG {dag.dag_id} is not loaded on the production cluster, due to `only_for_beta` tag."
        )


# [END example_dag_cluster_policy]


# [START example_task_cluster_policy]
class TimedOperator(BaseOperator, ABC):
    timeout: timedelta


def task_policy(task: TimedOperator):
    if task.task_type == "HivePartitionSensor":
        task.queue = "sensor_queue"
    if task.timeout > timedelta(hours=48):
        task.timeout = timedelta(hours=48)


# [END example_task_cluster_policy]


# [START example_task_mutation_hook]
def task_instance_mutation_hook(task_instance: TaskInstance):
    if task_instance.try_number >= 1:
        task_instance.queue = "retry_queue"


# [END example_task_mutation_hook]
