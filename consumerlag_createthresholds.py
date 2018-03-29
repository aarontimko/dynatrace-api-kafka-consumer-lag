import json
import requests
import urllib.parse
import pprint
import re

import common
from common.default import *


def try_request(f_url, f_headers, log_category, error_msg,
                log_key, log_value, f_dict, json_data="", m="get"):
    """
    Custom function to error handle Requests and output logging
    in a standardized format for Alexis

    Attributes:
        f_url (str): url for requests.get
        f_headers (dict): auth header in json format
        log_category (str): for logging, e.g. 'Poll' in "Poller::Poll"
        error_msg (str): descriptive error message if request fails
        log_key (str): key which ties all the log events together for reporting
                    e.g. feed_name, problem_id in Poller
        log_value (str): unique value for the log_key
                    e.g. "Test_AllOpenProblems_Syn.Day" -> feed_name value
                    e.g. "6685385694655871934"          -> problem_id value
        f_dict (dict): dictionary to store results
               note: must be defined before this function is called
        m (str): get, post, put, delete
    """

    # Attempt requests
    response = None

    # Determine method type
    if m == "get":
        requests_type = requests.get
    if m == "post":
        requests_type = requests.post
    if m == "put":
        requests_type = requests.put
    if m == "delete":
        requests_type = requests.delete

    try:
        if json_data == "":
            response = requests_type(f_url, headers=f_headers)
        else:
            response = requests_type(f_url, headers=f_headers, json=json_data)
    except requests.exceptions.RequestException as e:
        log_to_disk(log_category, lvl='ERROR',
                    msg="RequestsError "+log_key+"="+log_value,
                    kv=kvalue(exception=e))
        log_to_disk(log_category, lvl="ERROR",
                    msg=error_msg+" "+log_key+"="+log_value,
                    kv=kvalue(url=f_url))

    # If we received response, continue
    if response is not None:
        f_dict['results'] = response
        f_dict['status_code'] = f_dict['results'].status_code
        log_to_disk(log_category,
                    msg="HTTPResponse "+log_key+"="+log_value,
                    kv=kvalue(requests_status_code=f_dict['status_code']))

        # Non-HTTP 200 response
        if f_dict['status_code'] >= 400:
            log_to_disk(log_category, lvl="ERROR",
                        msg="RequestsResults "+log_key+"="+log_value,
                        kv=kvalue(requests_content=f_dict['results'].content))
            return False

        # Check for HTTP 2xx response
        if 200 <= f_dict['status_code'] <= 299:
            f_dict['elapsed'] = \
                str(f_dict['results'].elapsed.microseconds)[:-3]

            # Error handling for json in results.content
            try:
                f_dict['json'] = json.loads(f_dict['results'].content)
            except ValueError:
                f_dict['json'] = "{}"

            # Optional development logging: output raw f_dict['json']
            if app_conf['debug'] is True:
                print('JSON_CONTENT:' + str(f_dict['json']))

            log_to_disk(log_category,
                        msg="RequestsResults "+log_key+"="+log_value,
                        kv=kvalue(requests_elapsed_ms=f_dict['elapsed'])
                        )
        #return
        return True

    else:
        # response is None and no exception was caught
        log_to_disk(log_category, lvl="ERROR",
                    msg="requests response is None, no exception caught "+\
                        log_key+"="+log_value,
                    kv=kvalue(url=f_url))
        # return
        return False


def get_threshold_definitions(app_conf):

    threshold_list = None

    try:
        threshold_list = app_conf['threshold_list']
    except KeyError as e:
        log_to_disk('Conf', lvl='ERROR',
                    msg="Unable to grab 'threshold_list' from YAML file",
                    kv=kvalue(exception=e))

    if threshold_list is not None:
        return threshold_list
    else:
        return "ERROR: COULD NOT GRAB LIST"


def create_kafka_custom_threshold(url_tenant, f_headers,
                                  dt_threshold_list, consumer_group,
                                  log_category, error_msg,
                                  log_key, log_value,
                                  overwrite=False):

    # Define metric unique name for 'timeseriesId'
    metric_unique = \
        'custom:kafka.consumerlag.' + \
        consumer_group.lower() + \
        '.count'

    # Define threshold_url
    threshold_unique = 'kafka.consumerlag.' + consumer_group.lower()
    uri_threshold = '/api/v1/thresholds/' + threshold_unique
    f_url = urllib.parse.urljoin(url_tenant, uri_threshold)

    # Log that we are going to look at creating this metric
    log_to_disk(log_category,
                msg="Starting",
                kv=kvalue(consumer_group=consumer_group,
                          threshold=threshold_unique))


    # Assume we will not create the metric
    go_create_metric = False

    # Check if overwrite is True
    if overwrite == True:
        go_create_metric = True
    else:
        # Then overwrite = False, so check first if the metric exists
        # If it exists, log that fact and return False
        if threshold_unique in [x['thresholdId'] for x in dt_threshold_list]:
            log_to_disk(log_category,
                        msg="Threshold already created at" + \
                            " url_tenant=" + url_tenant,
                        kv=kvalue(status='skip',
                                  consumer_group=consumer_group,
                                  threshold=threshold_unique))
            return False
        else:
            # In this case, overwrite = False but the metric does Not exist
            # So we should go create the metric
            go_create_metric = True

    if go_create_metric == False:
        return False
    else:
        # Go Create the Metric (even if it exists already)

        # We ran into weird issues with values overriding,
        # so we always grab from scratch
        app_conf = grab_yaml_from_disk(conf_file)
        threshold_list = get_threshold_definitions(app_conf)

        # Set flag to False
        threshold_override = False
        threshold = None

        # Check if we use default or use threshold overrides
        for threshold_definition in threshold_list:
            if consumer_group == threshold_definition['consumer_group']:
                log_to_disk(log_category,
                            msg="Threshold override for" + \
                                " " + log_key + "=" + log_value,
                            kv=kvalue(threshold_definition=threshold_definition))

                threshold = threshold_definition
                threshold_override = True

        if threshold_override == False:
            # We assume the default settings are desired
            # Grab the list again from scratch
            app_conf = grab_yaml_from_disk(conf_file)
            threshold_list = app_conf['threshold_list']
            for threshold_definition in threshold_list:
                if app_conf['default_threshold'] == threshold_definition['consumer_group']:
                    # Grab default threshold
                    threshold = threshold_definition
                    # but then replace the 'consumer_group'
                    threshold['consumer_group'] = consumer_group

        # Determine if we are going to replace text
        if '$consumer_group' in threshold['eventName']:
            string = threshold['eventName']
            threshold['eventName'] = string.replace('$consumer_group', consumer_group)
        if '$consumer_group' in threshold['description']:
            string = threshold['description']
            threshold['description'] = string.replace('$consumer_group', consumer_group)

        # Grab the metric_unique name for the timeseriesId
        threshold['timeseriesId'] = metric_unique

        # Convert to JSON for requests
        json_definition = json.loads(json.dumps(threshold))

        # Submit Comment
        threshold_response = {}
        requests_response = False
        requests_response = try_request(
            f_url=f_url,
            f_headers=f_headers,
            log_category=log_category,
            error_msg=error_msg,
            log_key=log_key,
            log_value=log_value,
            f_dict=threshold_response,
            json_data=json_definition,
            m="put")

        # CHECK FOR VALID HTTP RESPONSE
        if requests_response == False:
            # Feed did not have valid HTTP response, we cannot continue
            return False
        else:
            requests_status_code = threshold_response['status_code']
            requests_content = threshold_response['json']
            if requests_status_code != 400:
                log_to_disk(log_category,
                            msg="Threshold created successfully" + \
                                " " + log_key + "=" + log_value,
                            kv=kvalue(status='success',
                                      consumer_group=consumer_group,
                                      threshold_url=f_url,
                                      requests_status_code=requests_status_code,
                                      requests_content=requests_content
                                      ))
            else:
                log_to_disk(log_category,
                            lvl='ERROR',
                            msg="RequestsError " + log_key + "=" + log_value,
                            kv=kvalue(status='failure',
                                      consumer_group=consumer_group,
                                      threshold_url=f_url,
                                      requests_status_code=requests_status_code,
                                      requests_content=requests_content
                                      ))




        # # Attempt requests
        # response = None
        #
        # try:
        #     response = requests.put(url=f_url, headers=f_headers,
        #                             json=json_definition)
        # except requests.exceptions.RequestException as e:
        #     log_to_disk(log_category, lvl='ERROR',
        #                 msg="RequestsError " + log_key + "=" + log_value,
        #                 kv=kvalue(exception=e))
        #     log_to_disk(log_category, lvl="ERROR",
        #                 msg=error_msg + " " + log_key + "=" + log_value,
        #                 kv=kvalue(url=url_tenant))
        #     return False
        #
        # # If we received response, continue
        # if response is not None:
        #     requests_status_code = response.status_code
        #     requests_content = response.content.decode('utf-8')
        #     if requests_status_code != 400:
        #         log_to_disk(log_category,
        #                     msg="Threshold created successfully" + \
        #                         " " + log_key + "=" + log_value,
        #                     kv=kvalue(status='success',
        #                               consumer_group=consumer_group,
        #                               threshold_url=f_url,
        #                               requests_status_code=requests_status_code,
        #                               requests_content=requests_content
        #                               ))
        #
        #         if app_conf['debug'] == True:
        #             print(requests_status_code)
        #             print(requests_content)
        #         f_dict = json.loads(requests_content)
        #         return f_dict
        #     else:
        #         log_to_disk(log_category, lvl='ERROR',
        #                     msg="RequestsError " + log_key + "=" + log_value,
        #                     kv=kvalue(status='failure',
        #                               consumer_group=consumer_group,
        #                               threshold_url=f_url,
        #                               requests_status_code=requests_status_code,
        #                               requests_content=requests_content))
        #
        #         if app_conf['debug'] == True:
        #             print(requests_status_code)
        #             print(requests_content)
        #         f_dict = json.loads(requests_content)
        #         return f_dict


def get_tenant_threshold_list(url_tenant, f_headers,
                              log_category, error_msg,
                              log_key, log_value,
                              search_threshold=''):


    # Define threshold_url
    uri_threshold = '/api/v1/thresholds'
    f_url = urllib.parse.urljoin(url_tenant, uri_threshold)


    # Requests Attempt
    threshold_response = {}
    http_response = False
    http_response = try_request(
        f_url=f_url,
        f_headers=f_headers,
        log_category=log_category,
        error_msg=error_msg,
        log_key=log_key,
        log_value=log_value,
        f_dict=threshold_response)

    # CHECK FOR VALID HTTP RESPONSE
    if http_response == False:
        return False
    else:
        threshold_list = threshold_response['json']

        # Determine if we are returning all thresholds or not
        if search_threshold == '':
            # Return all thresholds
            return_list = threshold_list
        else:
            filtered_threshold_list = []
            for threshold in threshold_list:
                message1 = search_threshold
                message2 = threshold['thresholdId']
                if re.search(message1, message2) is not None:
                    filtered_threshold_list.append(threshold)

            # Return filtered thresholds
            return_list = filtered_threshold_list

        log_to_disk(log_category,
                    msg="ThresholdResult",
                    kv=kvalue(search_threshold=search_threshold,
                              threshold_count=len(return_list),
                              url_tenant=url_tenant))

        return return_list




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

pp = pprint.PrettyPrinter(indent=4)

url_tenant = app_conf['url_tenant']


# DEV AND DEBUG VARIABLES

# Check for Debug flag, default to False if it is not set in app_conf
if 'debug' in app_conf:
    if app_conf['debug'] is True:
        common.default.app_debug = True
    else:
        common.default.app_debug = False
else:
    common.default.app_debug = False



#   -----------------------------------   #
#            SCRIPT ACTIONS
#   -----------------------------------   #


# Define Consumer Groups
consumer_group_list = ['MongoInserter','SyntheticEngine',
                       'MessageExtractor_key','duplicator_prod']


# Retrieve current threshold list
threshold_list = get_tenant_threshold_list(url_tenant=url_tenant,
                                           f_headers=f_headers,
                                           log_category='GetThresholds',
                                           error_msg="unable to get thresholds",
                                           log_key='url_tenant',
                                           log_value=url_tenant,
                                           search_threshold='kafka'
                                           )

# Go create Thresholds
for consumer_group in consumer_group_list:

    create_kafka_custom_threshold(url_tenant=url_tenant,
                                  f_headers=f_headers,
                                  dt_threshold_list=threshold_list,
                                  consumer_group=consumer_group,
                                  log_category='CreateThresholds',
                                  error_msg="unable to create threshold",
                                  log_key='consumer_group',
                                  log_value=consumer_group,
                                  overwrite=True)



# import pprint
# pp = pprint.PrettyPrinter(indent=4)
#
# pp.pprint(threshold_list)
#
# print(len(threshold_list))



# Output full list of threshold settings for validation
# pp.pprint(comprehensive_threshold_list)
# print(comprehensive_threshold_list)

