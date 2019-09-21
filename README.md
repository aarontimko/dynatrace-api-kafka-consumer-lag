# dynatrace-api-kafka-consumer-lag
Python service which pushes Consumer Lag for a Kafka Broker cluster to the Dynatrace Custom Metrics API

# Table of contents

- [Introduction](#introduction)
    - [Background](#background)
    - [Simple Run](#simple-run) 
    - [Example output](#example-output)
    - [Requirements](#requirements)
    - [Configuration](#configuration)
    - [Detail of Operations](#detail-of-operations)
      - [Main Loop](#main-loop)
    - [Versions](#configuration)    

# Introduction

If you have never worked with the Dynatrace Custom Network Device API, this project can help you with concepts and code to get you started.

We are using it to push multidimensional "Consumer Lag" metrics from Kafka Clusters to our Dynatrace Tenants.

But you could easily take the code and rework it into your own scenarios.


### Background

Full disclaimer - this isn't a full lesson in Kafka, it's just a simple picture.  There are far better introductory materials online, such as [kafka.apache.org](https://kafka.apache.org/documentation/#introduction)

Kafka is a message queue which contains message "topics".  A topic is just a temporary container for "messages".  There are Producers which push messages into these message topics, and then Consumers pull messages from those message topics. 

Consumers belong to Consumer Groups, and Consumer Groups function as a unit to consume messages from the message topics.  **"Consumer Lag"** is an integer metric which indicates how far behind the Consumer Group is from the front of the queue in that topic.  If the lag is "824", then the Consumer Group needs to consume 824 messages before it catches up to the front of the queue.  Generally, there is always some kind of acceptable lag, but if lag climbs too high, this means we have latency in that particular topic, and our data stream is not timely.

If you store this data in Kafka (instead of Zookeeper), you can retrieve the Consumer Lag using the `bin/kafka-consumergroups.sh` command and its parameters.

This project is designed to grab the output of the `bin/kafka-consumergroups.sh` command, parse the data, and push that data to a Custom Device using the [Dynatrace Custom Network Device and Metrics API](#https://www.dynatrace.com/support/help/dynatrace-api/timeseries/what-does-the-custom-network-devices-and-metrics-api-provide).

We could have accomplished this using the [Dynatrace OneAgent SDK](#https://dynatrace.github.io/plugin-sdk/index.html), and pushed metrics directly to the JVM pgi (process group instance) of each Broker.  This would have been a perfectly acceptable use case.  We could also push metrics directly to the JVM pgi of each Consumer.  But these are endeavors for other projects.

In this project, we wanted to tackle a multidimensional dataset and explore how to use the Dynatrace API to push that dataset into Dynatrace.  Consumer Lag is also interesting because the data entites are very dynamic - Consumer Groups and topics are often created and destroyed from week to week or month to month as different teams leverage the Kafka cluster.

So, Consumer Lag is interesting use case to show the flexibility and power of performing on-the-fly metric creation using the Dynatrace API (see [Example output](#example-output) and [Main Loop](#main-loop) for more info regarding the on-the-fly metric creation.)


### Simple Run

- Essential requirements: Python 3.6 with `requests` and `pyyaml`
- Ensure you have a custom device configured on your Tenant (see [Detail of Operations](#detail-of-operations))
- Configure this file: `consumerlag.yaml`
- Run:  `python consumerlag.py`

The logic of the script is to poll Kafka continuously.


### Example output

Example Output when new metrics are created (either on the initial loop or every 1000 executions)

```
2018-03-11 19:31:08,332 [INFO]  ConsumerLag::Loop - Starting url_tenant="https://zzz00000.live.dynatrace.com"
2018-03-11 19:31:08,332 [INFO]  ConsumerLag::GetConsumerGroups - ConsumerLag::GetConsumerGroups - Starting kafka_consumer_groups_list="['/opt/isv/tools/kafka/bin/kafka-consumer-groups.sh', '--bootstrap-server', 'localhost:9092', '--list', '--command-config', '/tmp/kafka-bin-client.prop']"
2018-03-11 19:31:11,870 [INFO]  ConsumerLag::GetConsumerGroups - Results consumer_group_list="['ActionEngine', 'DistributionLayerGroup',
'DynamicAnomalyEngine', 'DynamicAnomalyEngine2', 'HARSplitter', 'KMOffsetCache-wadvglmsb01.dev.saasapm.com', 'MessageExtractor_Key', 'MongoInserter',
'SAMInserter_day', 'SQLInserterGroup', 'SingleEnhancerConsumer.wayvmdwsenh01.dev.saasapm.com', 'SingleEnhancerConsumer.wayvmdwsenh02.dev.saasapm.com',
'SyntheticEngine', 'TargetConsumerGroup', 'duplicator', 'syntheticengine_WADVMDWSYN01']"
https://zzz00000.live.dynatrace.com/api/v1/timeseries/custom:kafka.consumerlag.actionengine.count
2018-03-11 19:31:12,191 [INFO]  ConsumerLag::APICall - Metric created successfully url_tenant=https://zzz00000.live.dynatrace.com status="success"
consumer_group="ActionEngine" metric="custom:kafka.consumerlag.actionengine.count"
https://zzz00000.live.dynatrace.com/api/v1/timeseries/custom:kafka.consumerlag.distributionlayergroup.count
2018-03-11 19:31:12,271 [INFO]  ConsumerLag::APICall - Metric created successfully url_tenant=https://zzz00000.live.dynatrace.com status="success"
consumer_group="DistributionLayerGroup" metric="custom:kafka.consumerlag.distributionlayergroup.count"
https://zzz00000.live.dynatrace.com/api/v1/timeseries/custom:kafka.consumerlag.dynamicanomalyengine.count
2018-03-11 19:31:12,415 [INFO]  ConsumerLag::APICall - Metric created successfully url_tenant=https://zzz00000.live.dynatrace.com status="success"
consumer_group="DynamicAnomalyEngine" metric="custom:kafka.consumerlag.dynamicanomalyengine.count"
2018-03-11 19:31:12,416 [INFO]  ConsumerLag::APICall - Metric already created at url_tenant=https://zzz00000.live.dynatrace.com status="skip"
consumer_group="DynamicAnomalyEngine2" metric="custom:kafka.consumerlag.dynamicanomalyengine2.count"
2018-03-11 19:31:12,416 [INFO]  ConsumerLag::APICall - Metric already created at url_tenant=https://zzz00000.live.dynatrace.com status="skip"
consumer_group="HARSplitter" metric="custom:kafka.consumerlag.harsplitter.count"
...
```

Example output when Consumer Lag is captured, built into a metrics push, and pushed to the Tenant.

```
2018-03-11 21:32:23,914 [INFO]  ConsumerLag::Loop - Starting url_tenant="https://zzz00000.live.dynatrace.com"
2018-03-11 21:32:23,915 [INFO]  ConsumerLag::GetConsumerGroups - ConsumerLag::GetConsumerGroups - Starting kafka_consumer_groups_list="['/opt/isv/tools/kafka/bin/kafka-consumer-groups.sh', '--bootstrap-server', 'localhost:9092', '--list', '--command-config', '/tmp/kafka-bin-client.prop']"
2018-03-11 21:32:26,949 [INFO]  ConsumerLag::GetConsumerGroups - Results consumer_group_list="['DynamicAnomalyEngine2', 'HARSplitter',
'MessageExtractor_Perf_DR', 'MessageExtractor_Perf_SaaS', 'MongoInserter', 'ProductHealthConsumerGroup', 'ProductHealthDFAGroup', 'SyntheticEngine',
'syntheticengine_wafpsymsyn01', 'syntheticengine_wafpsymsyn02', 'syntheticengine_wafpsymsyn03']"
...
2018-03-11 21:32:26,949 [INFO]  ConsumerLag::GetLag - Starting consumer_group="DynamicAnomalyEngine2"
2018-03-11 21:32:30,026 [INFO]  ConsumerLag::GetLag - Results consumer_group="DynamicAnomalyEngine2" consumer_group_lag="{'har_key': 58492}"
2018-03-11 21:32:30,027 [INFO]  ConsumerLag::GetLag - Starting consumer_group="HARSplitter"
2018-03-11 21:32:33,582 [INFO]  ConsumerLag::GetLag - Results consumer_group="HARSplitter" consumer_group_lag="{'dynamic_anomaly_engine': 189}"
...
2018-03-11 21:32:23,835 [INFO]:[DEBUG]  ConsumerLag::PushMetrics - JSON metrics_to_push="{'type': 'Kafka', 'series': [
      {'timeseriesId': 'custom:kafka.consumerlag.dynamicanomalyengine2.count', 'dimensions': {'topic': 'har_key'}, 'dataPoints': [[1520803905262, 54171]]},
      {'timeseriesId': 'custom:kafka.consumerlag.harsplitter.count', 'dimensions': {'topic': 'dynamic_anomaly_engine'}, 'dataPoints': [[1520803909335, 169]]},
      ...,
      {'timeseriesId': 'custom:kafka.consumerlag.syntheticengine.count', 'dimensions': {'topic': 'psr_ca'}, 'dataPoints': [[1520803934626, 254]]}]}"
2018-03-11 21:32:23,835 [INFO]  ConsumerLag::APICall - Attempting Push url_tenant=https://zzz00000.live.dynatrace.com
custom_device_url="https://zzz00000.live.dynatrace.com/api/v1/entity/infrastructure/custom/KafkaClusterPerf"
2018-03-11 21:32:23,914 [INFO]  ConsumerLag::APICall - Metrics pushed successfully url_tenant=https://zzz00000.live.dynatrace.com status="success"
custom_device="KafkaClusterPerf" requests_status_code="202" requests_content="{'entityId':'CUSTOM_DEVICE-7C2541922131FA96'}"
2018-03-11 21:32:23,914 [INFO]  ConsumerLag::Loop - Finished url_tenant="https://zzz00000.live.dynatrace.com" num_loops="33"
```

### Requirements

These are the basic requirements:

- Python 3.x
- requests
- pyyaml

From barebones, here is how to setup a CentOS system and execute the Python script.

```
cd REPO_DIR  (wherever you extracted the repo)
yum install python36u
python3.6 -m venv venv
. venv/bin/activate
pip install requests
pip install pyyaml
```

You can also see the `pip_env.sh` script as reference.

After you are completed with this manual testing, you can also wrap this in a bash script:

```
#!/bin/bash

cd /REPO_DIR;. venv/bin/activate;python consumerlag.py
```

And if you want to do something in systemd, you can make a service wrapper.
*(Note: There are more sophisticated manners of setting up Python services in systemd!
But this one works fine for a simple setup)*

```
vi /lib/systemd/system/dtsaas-consumerlag.service
```

```
[Unit]
Description=Python service to push custom metrics to Dynatrace (Kafka Consumer Lag)

[Service]
Type=simple
User=root
ExecStart=/usr/bin/bash -c 'cd /opt/alexis/dtsaas-consumerlag;. venv/bin/activate; python consumerlag.py'

[Install]
WantedBy=multi-user.target
```

```
systemctl daemon-reload
systemctl enable dtsaas-consumerlag.service
systemctl start dtsaas-consumerlag.service
```


### Configuration

See this Dynatrace API documentation link for more detail on the **Custom Network Devices and Metrics API**.
https://www.dynatrace.com/support/help/dynatrace-api/timeseries/what-does-the-custom-network-devices-and-metrics-api-provide

The main configuration file is `consumerlag.yaml`

- `authentication_list`: this is the Dynatrace API token that you need to create on your tenant.
See this URL to create your API token: https://zzz00000.live.dynatrace.com/#settings/integration/apikeys
Only one token is supported right now but in the future it could support multiple tokens (and Tenants)
- `url_tenant`: this is the full URL of your Tenant: https://zzz00000.live.dynatrace.com
- `kafka_consumer_groups_list`: this is the full command needed to execute `kafka-consumer-groups.sh --list`.  This is the new method as of v1.0.3 of this repository.  You can leave as 'localhost:9092' or you can specify your Broker `bootstrap` list.  This approach allows you to specify an extra `.prop` file if you have security configuration like an SSL keystore, SASL, etc.  You can also specify an alternate location of *kafka-consumer-groups.sh*.
- `kafka_consumer_groups_describe`: this is the full command needed to execute `kafka-consumer-groups.sh --describe`.  This is the new method as of v1.0.3 of this repository.  You can leave as 'localhost:9092' or you can specify your Broker `bootstrap` list.  This approach allows you to specify an extra `.prop` file if you have security configuration like an SSL keystore, SASL, etc.  You can also specify an alternate location of *kafka-consumer-groups.sh*.
- `custom_device` Every Dynatrace Custom Device needs a unique name when you push to it.
https://zzz00000.live.dynatrace.com/api/v1/entity/infrastructure/custom/MY_CUSTOMDEVICENAME_WHICH_I_MADE_UP_MYSELF
- `check_metrics_every_x_loops`: The script will query for all Metrics and compare that list against the current Consumer Group list.  If there are new Consumer Groups, the code will create new custom metrics on-the-fly for those new Consumer Groups.
- `development: False`: this should only be True if you're testing in your Python IDE and you want dummy data to work with
- `kafka_only: True`: this should be used if you want to validate your Kafka interaction before any interaction with Dynatrace.  In other words, setting to True means that no calls will be made to the Dynatrace tenant.  When you're ready to begin interaction with your Dynatrace tenant, set to `False`.
- `debug: True`: There are a few debug log lines.  Set to `False` to be more minimal in your logging.
- `default_threshold`: name of the default threshold settings in the `threshold_list`
- `threshold_list`: a default threshold and other threshold overrides


### Detail of Operations

Currently this project only supports a 1:1 relationship of:
- 1 Python instance
- 1 YAML file
- 1 Broker Bootstrap URL
- 1 Custom Device Endpoint
- 1 Tenant

In sum, the `consumerlag.py` code takes data from a single Kafka cluster and pushes to a single Custom Device on a Dynatrace Tenant.

These are the basic steps to pushing these metrics:

- Edit `consumerlag.yaml` with your Authentication token, Tenant URL, bootstrap URL, and custom_device unique name.
  - Be sure to set: `development: False` -> this should only be True if you're testing in your Python IDE and you want dummy data to work with

- Create a `custom:device.heartbeat.count` metric on each Tenant.
  - You can find the code to create this specific metric in `consumerlag_singleexecutions.py`.
  Look for the simple code example marked by `com.dynatrace.api.custom.metric.create.customdeviceheartbeatcount`.
  We use this during custom device creation, and it could certainly be used as a key metric for Active Monitoring
  that your Kafka Consumer lag script is up and operational (see https://github.com/aarontimko/dynatrace-api-validate-timeseries)

- Create the custom device at a unique URL and register it with the `custom:device.heartbeat.count` metric.
  - You can find the code in `consumerlag_singleexecutions.py` within the `define_custom_device` function examples.
  If the API call is successful, you receive a 202 HTTP status code response and the `entityId` of your new custom device.
  Record the "CUSTOM_DEVICE-GUID" if you want to reach the Custom Device URL at: https://zzz00000.live.dynatrace.com/#entity;id=**CUSTOM_DEVICE-GUID**;gtf=l_2_HOURS

- Determine your threshold values and settings under `threshold_list` in the `consumerlag.yaml` file.
  - Update as necessary

- Run: `python consumerlag.py`
  - This will query Kafka for all Consumer Groups and ensure they exist on the destination Tenant in this format:
  custom:kafka.consumerlag.**CONSUMER_GROUP_NAME**.count
  - Then it will obtain the lag for each Consumer Group's topics, sum the lag per topic, and build a timeseries JSON of all this data
  - Lastly, it pushes all of these metrics in 1 call to the Dynatrace API.
  (See [Main Loop](#main-loop) for more detail)


#### Main Loop

The `consumerlag.py` script will do the following:
- grab the configuration values from the `consumerlag.yaml` file
- start loop 
- reference the `bootstrap` URL of the Kafka cluster
- query Kafka for Consumer Groups `obtain_kafka_consumer_groups()`
(this uses the Kafka command: `/opt/broker/bin/kafka-consumer-groups.sh --new-consumer --list`)
- on the 1st run and every X runs (denoted by `check_metrics_every_x_loops`)
  - grab the full list of metrics `obtain_timeseries_metrics()`
  - create a metric for each Consumer Group if it does not exist `create_kafkalag_metric()`
- on the 1st run, the script will ALSO create custom thresholds for every metric by doing the following:
  - grab the `threshold_list` from the `consumerlag.yaml` file
  - use the `default_threshold` settings to dynamically create thresholds for each metric
  - if overridden with a manual entry (e.g. `consumer_group: 'MongoInserter'`), it will use those values instead for that consumer_group
- query Kafka for the lag for each Consumer Group, sum the lag for each topic `obtain_kafka_consumer_lag()`
(this uses the Kafka command: `/opt/broker/bin/kafka-consumer-groups.sh --new-consumer --describe --group`)
- append each metric for each ConsumerGroup+Topic to the custom metric json syntax `append_custom_metrics()`
- at the end of all the individual metric appends, push with 1 API call the full custom metrics JSON to the Dynatrace custom device `push_custom_metrics()`
- restart loop


### Versions

v1.01 - Initial commit
v1.02 - Added the ability to create custom thresholds on-the-fly, driven by configuration (see `threshold_list`)
