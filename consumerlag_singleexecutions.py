import urllib.parse
import json
import requests
import pprint

import common
from common.default import *

#   -----------------------------------   #
#            LOCAL FUNCTIONS
#   -----------------------------------   #


def obtain_kafka_consumer_groups(bootstrap):
    """
    Obtains the output from this Kafka utility command:
     /opt/broker/bin/kafka-consumer-groups.sh --new-consumer --list

    @retval sorted Python list of kafka consumer groups
    """

    # See app_conf['development'] setting for this
    if app_conf['development'] == True:

        # This is for simulating return data
        decode = 'MongoInserter\n' \
                 'ProductHealthDFAGroup\n' \
                 'syntheticengine_wafpsymsyn03\n' \
                 'MessageExtractor_Perf_SaaS\n' \
                 'ProductHealthConsumerGroup\n' \
                 'syntheticengine_wafpsymsyn01\n' \
                 'HARSplitter\n' \
                 'SyntheticEngine\n' \
                 'DynamicAnomalyEngine2\n' \
                 'syntheticengine_wafpsymsyn02\n'

        split_list = decode.split("\n")

    else:
        # This is the live production execution

        string = None

        try:
            string = subprocess.check_output([
                "/opt/broker/bin/kafka-consumer-groups.sh",
                "--new-consumer",
                "--bootstrap-server",
                bootstrap,
                "--list"
            ])
        except Exception as e:
            print('Unable to grab consumer groups: '+e.__str__())

        if string is not None:
            # Decode, then split by \n into a list
            split_list = string.decode('utf-8').split("\n")
        else:
            return False

    # Whether for dev or for live run,
    # split_list should be available now for further processing

    # Remove any empty strings (e.g. at end of subprocess output)
    group_list = list(filter(None, split_list))
    # Sort list
    sorted_list = sorted(group_list)

    return sorted_list


def obtain_timeseries_metrics(url_tenant, f_headers,
                              log_category, error_msg,
                              log_key, log_value):

    # timeseries URL
    uri_timeseries = 'api/v1/timeseries'
    f_url = urllib.parse.urljoin(url_tenant, uri_timeseries)

    # Attempt requests
    response = None

    try:
        response = requests.get(f_url, headers=f_headers)
    except requests.exceptions.RequestException as e:
        log_to_disk(log_category, lvl='ERROR',
                    msg="RequestsError "+log_key+"="+log_value,
                    kv=kvalue(exception=e))
        log_to_disk(log_category, lvl="ERROR",
                    msg=error_msg+" "+log_key+"="+log_value,
                    kv=kvalue(url=f_url))

    # If we received response, continue
    if response is not None:
        f_dict = json.loads(response.content.decode('utf-8'))
        return f_dict

def create_kafkalag_metric(url_tenant, f_headers, dt_metrics_list,
                           consumer_group,
                           log_category, error_msg,
                           log_key, log_value):

    # Define metric name with standard convention
    metric_unique = \
        'custom:kafka.consumerlag.' + \
        consumer_group.lower() + \
        '.count'

    # Check if metric already exists
    if metric_unique in [x['timeseriesId'] for x in dt_metrics_list]:
        log_to_disk(log_category,
                    msg="Metric already created at" + \
                        " " + log_key + "=" + log_value,
                    kv=kvalue(status='skip',
                              consumer_group=consumer_group,
                              metric=metric_unique))
        return False
    else:
        # metric does not exist in Dynatrace yet
        # proceed with creating
        definition = '{' \
                 '"displayName" : "Lag - ' + consumer_group + '",' \
                 '"unit" : "Count",' \
                 '"dimensions": [' \
                 '"topic"' \
                 '],' \
                 '"types": [' \
                 '"Kafka"' \
                 ']' \
                 '}'
        json_definition = json.loads(definition)
        # if app_conf['debug'] == True:
        #     if pp:
        #         pp.pprint(json_definition)

        # Create metric endpoint URL
        uri_metric = '/' + metric_unique
        uri_timeseries = 'api/v1/timeseries'
        url_timeseries = urllib.parse.urljoin(url_tenant, uri_timeseries)
        f_url = url_timeseries + uri_metric
        if app_conf['debug'] == True:
            print(f_url)

        # Attempt requests
        response = None

        try:
            response = requests.put(url=f_url, headers=f_headers,
                                    json=json_definition)
        except requests.exceptions.RequestException as e:
            log_to_disk(log_category, lvl='ERROR',
                        msg="RequestsError " + log_key + "=" + log_value,
                        kv=kvalue(exception=e))
            log_to_disk(log_category, lvl="ERROR",
                        msg=error_msg + " " + log_key + "=" + log_value,
                        kv=kvalue(url=url_tenant))
            return False

        # If we received response, continue
        if response is not None:
            log_to_disk(log_category,
                        msg="Metric created successfully" + \
                            " " + log_key + "=" + log_value,
                        kv=kvalue(status='success',
                                  consumer_group=consumer_group,
                                  metric=metric_unique))
            f_dict = json.loads(response.content.decode('utf-8'))
            return f_dict


def delete_kafkalag_metric(url_tenant, f_headers, consumer_group,
                           log_category, error_msg,
                           log_key, log_value):

    # Define metric name with standard convention
    metric_unique = \
        'custom:kafka.consumerlag.' + \
        consumer_group.lower() + \
        '.count'

    # Create metric endpoint URL
    uri_metric = '/' + metric_unique
    uri_timeseries = 'api/v1/timeseries'
    url_timeseries = urllib.parse.urljoin(url_tenant, uri_timeseries)
    f_url = url_timeseries + uri_metric
    if app_conf['debug'] == True:
        print(f_url)

    # Attempt requests
    response = None

    try:
        response = requests.delete(url=f_url, headers=f_headers)
    except requests.exceptions.RequestException as e:
        log_to_disk(log_category, lvl='ERROR',
                    msg="RequestsError " + log_key + "=" + log_value,
                    kv=kvalue(exception=e))
        log_to_disk(log_category, lvl="ERROR",
                    msg=error_msg + " " + log_key + "=" + log_value,
                    kv=kvalue(url=url_tenant))
        return False

    # If we received response, continue
    if response is not None:
        log_to_disk(log_category,
                    msg="Metric deleted successfully" + \
                        " " + log_key + "=" + log_value,
                    kv=kvalue(status='success',
                              consumer_group=consumer_group,
                              metric=metric_unique))
        print(response.status_code)
        print(response.content.decode('utf-8'))
        return response


def define_custom_device(url_tenant, f_headers, unique_name, display_name,
                         ip_addresses, listen_ports, type, config_url, tags,
                         properties,
                         log_category, error_msg,
                         log_key, log_value):

    post_url = url_tenant + \
               '/api/v1/entity/infrastructure/custom/' + \
               unique_name

    metrics = '{' \
              '"displayName" : "' + display_name + '",' \
              '"ipAddresses" : ' + ip_addresses + ',' \
              '"listenPorts" : ' + listen_ports + ',' \
              '"type" : "' + type + '",' \
              '"configUrl" : "' + config_url + '",' \
              '"tags": ' + tags + ',' \
              '"properties" : ' + properties + ',' \
              '"series" : [' \
              '{' \
              '"timeseriesId" : "custom:device.heartbeat.count",' \
              '"dataPoints" : [ [' + str(get_epochms()) + ', 1] ]' \
              '}' \
              ']' \
              '}'


    # '"favicon" : "https://svn.apache.org/repos/asf/kafka/site/logos/originals/png/TALL%20-%20Black%20on%20Transparent.png",' \

    json_metrics = json.loads(metrics)

    response = None

    try:
        response = requests.post(url=post_url,
                             headers=f_headers,
                             json=json_metrics)
    except requests.exceptions.RequestException as e:
        log_to_disk(log_category, lvl='ERROR',
                    msg="RequestsError " + log_key + "=" + log_value,
                    kv=kvalue(exception=e))
        log_to_disk(log_category, lvl="ERROR",
                    msg=error_msg + " " + log_key + "=" + log_value,
                    kv=kvalue(url=url_tenant))
        return False

    if response is not None:
        print(response.status_code)
        print(response.content.decode('utf-8'))
        return response



def get_epochms(offset_sec="0"):

    offset_ms = int(offset_sec) * 1000
    now_ms = int(round(time.time() * 1000, 0))
    final_time_ms = now_ms - offset_ms
    return final_time_ms



# -----------------------------------   #
#            VARIABLES
#   -----------------------------------   #


# GENERAL VARIABLES
common.default.app_name = "ConsumerLag"
common.default.app_logdir = "log"

# app_name_2017-11-06.log
app_logfile_string = common.default.app_name.lower() + \
                     "_" + str(get_date()) + ".log"

common.default.app_logfile = os.path.join(common.default.app_logdir,
                                          app_logfile_string)


# RUNTIME VARIABLES
conf_file = 'consumerlag.yaml'
app_conf = grab_yaml_from_disk(conf_file)

authentication_list = app_conf['authentication_list']
authentication = authentication_list[0]
headers = authentication['headers']
f_headers = json.loads(headers.replace("'", '"'))

url_tenant = app_conf['url_tenant']
pp = pprint.PrettyPrinter(indent=4)


#   -----------------------------------   #
#            SCRIPT ACTIONS
#   -----------------------------------   #


# CREATE CUSTOM DEVICE HEARTBEAT COUNT
# com.dynatrace.api.custom.metric.create.customdeviceheartbeatcount
expand_start = True
#  # VARIABLES
# headers_sample = '{"Authorization":"Api-Token sdfj3kvkdrj34kjdfkw35"}'
# f_headers = json.loads(headers_sample.replace("'", '"'))
#
# url_tenant = 'https://zzz00000.live.dynatrace.com'
#
# pp = pprint.PrettyPrinter(indent=4)
#
#
# # Define metric name with standard convention
# metric_unique = 'custom:device.heartbeat.count'
#
# definition = '{' \
#              '"displayName" : "Custom Device - Heartbeat",' \
#             '"unit" : "Count",' \
#             '"types": [' \
#             '"Custom"' \
#             ']' \
#             '}'
#
# json_definition = json.loads(definition)
#
# if pp:
#     pp.pprint(json_definition)
# else:
#     print(json_definition)
#
# # Create metric endpoint URL
# uri_metric = '/' + metric_unique
# uri_timeseries = 'api/v1/timeseries'
# url_timeseries = urllib.parse.urljoin(url_tenant, uri_timeseries)
# f_url = url_timeseries + uri_metric
# print(f_url)
#
# # Attempt requests
# response = None
#
# try:
#     response = requests.put(url=f_url, headers=f_headers,
#                             json=json_definition)
# except requests.exceptions.RequestException as e:
#     print('ERROR: '+e)
#
#
# f_dict = json.loads(response.content.decode('utf-8'))
# print(f_dict)
expand_end = True


# CREATE CUSTOM DEVICES (barebones function)
expand_start = True
# define_device_result = define_custom_device(
#     url_tenant='https://zzz00000.live.dynatrace.com',
#     f_headers=json.loads('{"Authorization":"Api-Token sdfj3kvkdrj34kjdfkw35"}'.replace("'", '"')),
#     unique_name='KafkaClusterTest01',
#     display_name='Test',
#     ip_addresses='["10.201.200.50"]',
#     listen_ports='["7070"]',
#     type='Kafka',
#     config_url='wadvmdwbrk01.dev.saasapm.com',
#     tags='["syn.test", "syn.middleware", "syn.kafka"]',
#     properties='{ "test_custom_device" : "True" }',
#     log_category='APICall',
#     error_msg="unable to create custom device",
#     log_key='url_tenant',
#     log_value=url_tenant)
#
# define_device_result = define_custom_device(
#     url_tenant='https://zzz00000.live.dynatrace.com',
#     f_headers=json.loads('{"Authorization":"Api-Token sdfj3kvkdrj34kjdfkw35"}'.replace("'", '"')),
#     unique_name='KafkaClusterDay',
#     display_name='Day',
#     ip_addresses='["10.201.200.54"]',
#     listen_ports='["7070"]',
#     type='Kafka',
#     config_url='wadvmdwbrk01.dev.saasapm.com',
#     tags='["syn.day", "syn.middleware", "syn.kafka"]',
#     properties='{ "test_custom_device" : "True" }',
#     log_category='APICall',
#     error_msg="unable to create custom device",
#     log_key='url_tenant',
#     log_value=url_tenant)
#
# define_device_result = define_custom_device(
#     url_tenant='https://zzz00000.live.dynatrace.com',
#     f_headers=json.loads('{"Authorization":"Api-Token sdfj3kvkdrj34kjdfkw35"}'.replace("'", '"')),
#     unique_name='KafkaClusterSprint',
#     display_name='Sprint',
#     ip_addresses='["10.201.200.86"]',
#     listen_ports='["7070"]',
#     type='Kafka',
#     config_url='wadvmdwbrk11.dev.saasapm.com',
#     tags='["syn.sprint", "syn.middleware", "syn.kafka"]',
#     properties='{ "test_custom_device" : "True" }',
#     log_category='APICall',
#     error_msg="unable to create custom device",
#     log_key='url_tenant',
#     log_value=url_tenant)
#
# define_device_result = define_custom_device(
#     url_tenant='https://zzz00000.live.dynatrace.com',
#     f_headers=json.loads('{"Authorization":"Api-Token sdfj3kvkdrj34kjdfkw35"}'.replace("'", '"')),
#     unique_name='KafkaClusterPerf',
#     display_name='Perf',
#     ip_addresses='["10.200.200.146"]',
#     listen_ports='["9092"]',
#     type='Kafka',
#     config_url='wafpmdwbrk01.prod.saasapm.com',
#     tags='["syn.perf", "syn.middleware", "syn.kafka"]',
#     properties='{ "test_custom_device" : "True" }',
#     log_category='APICall',
#     error_msg="unable to create custom device",
#     log_key='url_tenant',
#     log_value=url_tenant)
#
# define_device_result = define_custom_device(
#     url_tenant='https://zzz00000.live.dynatrace.com',
#     f_headers=json.loads('{"Authorization":"Api-Token sdfj3kvkdrj34kjdfkw35"}'.replace("'", '"')),
#     unique_name='KafkaClusterProd',
#     display_name='Kafka (Prod)',
#     ip_addresses='["10.200.200.23"]',
#     listen_ports='["9092"]',
#     type='Kafka',
#     config_url='wappmdwbrk01.prod.saasapm.com',
#     tags='["syn.prod", "syn.middleware", "syn.kafka"]',
#     properties='{ "test_custom_device" : "True" }',
#     log_category='APICall',
#     error_msg="unable to create custom device",
#     log_key='url_tenant',
#     log_value=url_tenant)
expand_end = True


# CREATE CONSUMER GROUP METRICS MANUALLY
expand_start = True
# Grab Consumer Group List
# consumer_group_list = \
#     obtain_kafka_consumer_groups(bootstrap="localhost:9092")
# print(consumer_group_list)
#
# consumer_group_list = ['MongoInserter','SyntheticEngine','ActionEngine',
#                           'MessageExtractor_key','duplicator_prod',
#                           'ProductHealthConsumerGroup','TargetConsumerGroup',
#                           'HARSplitter','SQLInserterGroup',
#                           'MessageExtractorProd', 'ProductHealthDFAGroup',
#                           'MongoInserter_dr','DynamicAnomalyEngine',
#                           'DynamicAnomalyEngine2','DistributionLayerGroup',
#                           'duplicator','SAMInserter_prod','SAMInserter_eap']
#
#
# consumer_group_list = ['MongoInserter','SyntheticEngine','ActionEngine']
#
# for consumer_group in consumer_group_list:
#
    dt_metrics_list = obtain_timeseries_metrics(
        url_tenant=url_tenant,
        f_headers=f_headers,
        log_category='APICall',
        error_msg="unable to obtain metrics list",
        log_key='url_tenant',
        log_value=url_tenant)
#
#     create_metric_response = create_kafkalag_metric(
#         url_tenant=url_tenant,
#         f_headers=f_headers,
#         dt_metrics_list=dt_metrics_list,
#         consumer_group=consumer_group,
#         log_category='APICall',
#         error_msg="unable to create metric",
#         log_key='url_tenant',
#         log_value=url_tenant)
#
#     print(create_metric_response)
#
#
# # Check manually if a metric already exists in the current metrics list
#
# metric_exists = 'custom:kafka.consumerlag.mongoinserter.count'
# if metric_exists in [x['timeseriesId'] for x in dt_metrics_list]:
#     print("YES, this metric already exists: " + metric_exists)
#
expand_end = True


# DELETE CONSUMER GROUPS
expand_start = True
# Grab Consumer Group List
# consumer_group_list = \
#     obtain_kafka_consumer_groups(bootstrap="localhost:9092")
# print(consumer_group_list)
#
# consumer_group_list = ['MongoInserter','SyntheticEngine','ActionEngine',
#                           'MessageExtractor_key','duplicator_prod',
#                           'ProductHealthConsumerGroup','TargetConsumerGroup',
#                           'HARSplitter','SQLInserterGroup',
#                           'MessageExtractorProd', 'ProductHealthDFAGroup',
#                           'MongoInserter_dr','DynamicAnomalyEngine',
#                           'DynamicAnomalyEngine2','DistributionLayerGroup',
#                           'duplicator','SAMInserter_prod','SAMInserter_eap']
#
#
# #consumer_group_list = ['MongoInserter','SyntheticEngine','ActionEngine']
#
# for consumer_group in consumer_group_list:
#
#     delete_metric_response = delete_kafkalag_metric(
#         url_tenant=url_tenant,
#         f_headers=f_headers,
#         consumer_group=consumer_group,
#         log_category='APICall',
#         error_msg="unable to create metric",
#         log_key='url_tenant',
#         log_value=url_tenant)
#
#     print(delete_metric_response)
expand_end = True


