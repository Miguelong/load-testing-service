import json
import os

import MySQLdb
import matplotlib
from tempfile import TemporaryFile
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import traceback
import sys

from LoadTest import *

matplotlib.use('Agg')
from django.http import FileResponse

TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'temp')


def produce_success_response(data):
    response_body = {'meta': {'code': 200}, 'data': data}
    return HttpResponse(json.dumps(response_body), content_type="application/json")


def produce_fail_response(data):
    response_body = {'meta': {'code': 500}, 'data': data}
    return HttpResponse(json.dumps(response_body), content_type="application/json")


@csrf_exempt
def setup(request):
    user = request.POST.get('user')
    test_name = request.POST.get('testName')
    description = request.POST.get('description', '')
    url = request.POST.get('apiUrl')
    concurrent_num = int(request.POST.get('concurrentNum'))
    method = request.POST.get('apiMethod')
    header = request.POST.get('apiHeader', '')
    payload = request.POST.get('apiPayload', '')
    timeout = int(request.POST.get('apiTimeout'))
    proxy = request.POST.get('apiProxy', '')
    parameters = request.FILES.get('parameters')
    repeat = int(request.POST.get('repeat', '1'))

    db = MySQLdb.connect("model-mysql.internal.gridx.com", "demo", "RE3u6pc8ZYx1c", "test")
    cursor = db.cursor()

    if parameters is None:
        insert_sql = "insert load_test (user,testName,description,apiUrl,concurrentNum,apiMethod," \
                     " apiHeader, apiPayload, apiTimeout, apiProxy, `repeat`)" \
                     " values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    else:
        insert_sql = "insert load_test (user,testName,description,apiUrl,concurrentNum,apiMethod," \
                     " apiHeader, apiPayload, apiTimeout,apiProxy, parameters, `repeat`)" \
                     " values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

    try:
        if parameters is None:
            cursor.execute(insert_sql,
                           [user, test_name, description, url, concurrent_num, method, header, payload, timeout, proxy,
                            repeat])
        else:
            cursor.execute(insert_sql,
                           [user, test_name, description, url, concurrent_num, method, header, payload, timeout, proxy,
                            MySQLdb.Binary(parameters.read()), repeat])

        test_id = int(db.insert_id())
        print test_id
        db.commit()

    except Exception, e:
        error = repr(e)
        print error
        db.rollback()

    db.close()

    response_data = {}

    if 'test_id' not in vars():
        response_data['error'] = error
        return produce_fail_response(response_data)
    else:
        response_data['testId'] = test_id
        return produce_success_response(response_data)


@csrf_exempt
def get_test_case(request):
    test_id = request.GET.get('testId')
    db = MySQLdb.connect("model-mysql.internal.gridx.com", "demo", "RE3u6pc8ZYx1c", "test")
    cursor = db.cursor()
    cursor.execute("select user,testName,description,apiUrl,concurrentNum,apiMethod,apiHeader,apiPayload,apiTimeout,"
                   "apiProxy,`repeat` from load_test where id=%s" %
                   str(test_id))
    res = cursor.fetchone()
    user = res[0]
    test_name = res[1]
    description = res[2]
    url = res[3]
    concurrent_num = res[4]
    method = res[5]
    header = res[6]
    payload = res[7]
    timeout = res[8]
    proxy = res[9]
    repeat = res[10]

    response_data = {'user': user, 'testName': test_name, 'description': description,
                     'apiUrl': url, 'concurrentNum': concurrent_num, 'apiMethod': method,
                     'apiHeader': header, 'apiPayload': payload, 'apiTimeout': timeout,
                     'apiProxy': proxy, 'repeat': repeat}
    return produce_success_response(response_data)


@csrf_exempt
def update_test_case(request):
    test_id = request.POST.get('testId')
    user = request.POST.get('user')
    test_name = request.POST.get('testName')
    description = request.POST.get('description', '')
    url = request.POST.get('apiUrl')
    concurrent_num = int(request.POST.get('concurrentNum'))
    method = request.POST.get('apiMethod')
    header = request.POST.get('apiHeader', '')
    payload = request.POST.get('apiPayload', '')
    timeout = int(request.POST.get('apiTimeout'))
    proxy = request.POST.get('apiProxy', '')
    parameters = request.FILES.get('parameters')
    repeat = int(request.POST.get('repeat', '1'))

    db = MySQLdb.connect("model-mysql.internal.gridx.com", "demo", "RE3u6pc8ZYx1c", "test")
    cursor = db.cursor()
    # If no parameters file uploaded, keep the original file
    if parameters is None:
        update_sql = "update load_test set user=%s, testName=%s, description=%s, apiUrl=%s,concurrentNum=%s," \
                     "apiMethod=%s, apiHeader=%s,apiPayload=%s,apiTimeout=%s,apiProxy=%s, `repeat`=%s where id=%s"
    else:
        update_sql = "update load_test set user=%s, testName=%s, description=%s, apiUrl=%s,concurrentNum=%s," \
                     "apiMethod=%s,apiHeader=%s,apiPayload=%s,apiTimeout=%s,apiProxy=%s,parameters=%s,`repeat`=%s" \
                     " where id=%s"

    try:
        if parameters is None:
            cursor.execute(update_sql, [user, test_name, description, url, concurrent_num, method, header, payload,
                                        timeout, proxy, repeat, test_id])
        else:
            cursor.execute(update_sql, [user, test_name, description, url, concurrent_num, method, header, payload,
                                        timeout, proxy, MySQLdb.Binary(parameters.read()), repeat, test_id])
        db.commit()

    except Exception, e:
        error = repr(e)
        print error
        db.rollback()
        response_data = {'error': error}
        return produce_fail_response(response_data)

    db.close()

    response_data = {'testId': test_id}
    return produce_success_response(response_data)


@csrf_exempt
def get_all_cases(request):
    data = json.loads(request.body)
    page = int(data.get('pagination').get('page'))
    perPage = int(data.get('pagination').get('perPage'))
    start = perPage * (page - 1)
    print start

    db = MySQLdb.connect("model-mysql.internal.gridx.com", "demo", "RE3u6pc8ZYx1c", "test")
    cursor = db.cursor()

    cursor.execute("select count(*) from load_test")
    res = cursor.fetchone()
    totalSize = int(res[0])

    sql = "select id,user,testName,status,progress,description from load_test order by id limit " + str(
        start) + "," + str(perPage)
    cursor.execute(sql)
    results = cursor.fetchall()
    response_data = {}
    list = []
    for row in results:
        id = row[0]
        user = row[1]
        testName = row[2]
        status = row[3]
        progress = row[4]
        description = row[5]
        list.append({"testId": id, "user": user, "testName": testName, "status": status, "progress": progress,
                     "description": description})

    response_data = {"list": list, "pagination": {"totalSize": totalSize}}

    db.close()
    return produce_success_response(response_data)


@csrf_exempt
def download_report(request):
    test_id = request.GET.get('testId')
    db = MySQLdb.connect("model-mysql.internal.gridx.com", "demo", "RE3u6pc8ZYx1c", "test")
    cursor = db.cursor()
    cursor.execute("select report from load_test where id=" + str(test_id))
    res = cursor.fetchone()
    report = res[0]

    file = open(os.path.join(TEMP_DIR, report), 'rb')
    response = FileResponse(file)
    response['Content-Type'] = 'application/octet-stream'
    response['Content-Disposition'] = 'attachment;filename="report.docx"'
    return response


@csrf_exempt
def start_test(request):
    # get testId
    data = json.loads(request.body)
    test_id = data.get('testId')

    # set status of test to 'running'
    db = MySQLdb.connect("model-mysql.internal.gridx.com", "demo", "RE3u6pc8ZYx1c", "test")
    cursor = db.cursor()
    try:
        cursor.execute("select status from load_test where id=" + str(test_id))
        res = cursor.fetchone()
        status = res[0]
        # if the test is already running leave it
        if status == 'running':
            response_data = {'error': 'The test case is already running. Please wait until it is completed.'}
            return produce_fail_response(response_data)

        cursor.execute("update load_test set progress=0.0, status='running' where id=" + str(test_id))
        db.commit()
    except Exception, e:
        print repr(e)
        db.rollback()
        response_data = {'stage': 'update status', 'error': repr(e)}
        return produce_fail_response(response_data)

    # get configuration of the test
    sql = "select apiUrl,concurrentNum,apiMethod,apiHeader,apiPayload,apiTimeout,apiProxy,parameters,report,`repeat` " \
          "from load_test where id=" + str(test_id)
    cursor.execute(sql)
    res = cursor.fetchone()
    url = res[0]
    concurrent_num = int(res[1])
    method = res[2]
    header = res[3]
    payload = res[4]
    timeout = int(res[5])
    proxy = res[6]
    parameters = res[7]
    report = res[8]
    # parameters should be repeated n times
    repeat = int(res[9])

    db.close()

    # delete report and images of last test
    if report is not None and report != '':
        prefix = report.split('.')[0]
        success_img = prefix + '_Success.png'
        success_trend_img = prefix + '_Success_trend.png'
        timeout_img = prefix + '_Timeout.png'
        timeout_trend_img = prefix + '_Timeout_trend.png'
        try:
            os.listdir(TEMP_DIR)
            os.remove(os.path.join(TEMP_DIR, report))
        except Exception, e:
            traceback.print_exc(file=sys.stdout)

        try:
            os.listdir(TEMP_DIR)
            os.remove(os.path.join(TEMP_DIR, success_img))
        except Exception, e:
            traceback.print_exc(file=sys.stdout)

        try:
            os.listdir(TEMP_DIR)
            os.remove(os.path.join(TEMP_DIR, success_trend_img))
        except Exception, e:
            traceback.print_exc(file=sys.stdout)

        try:
            os.listdir(TEMP_DIR)
            os.remove(os.path.join(TEMP_DIR, timeout_img))
        except Exception, e:
            traceback.print_exc(file=sys.stdout)

        try:
            os.listdir(TEMP_DIR)
            os.remove(os.path.join(TEMP_DIR, timeout_trend_img))
        except Exception, e:
            traceback.print_exc(file=sys.stdout)

    # parameters_list is a list of parameters that the get or post request requires
    parameters_list = []
    incre_list = []

    if parameters is None:  # the url of get has no parameters
        incre_list.append('[]')
    else:
        lines = parameters.split('\n')
        for line in lines:
            if line != '':
                incre_list.append(line)

    # parameters should be repeated n times
    for i in range(repeat):
        parameters_list += incre_list

    # set to None of empty parameters
    if header == '':
        header = None

    if payload == '':
        payload = None

    if proxy == '':
        proxy = None

    # start the load test
    test = LoadTest(url, concurrent_num, method, header, payload, timeout, proxy, parameters_list, test_id)
    test.start_test()

    response_data = {'status': 'running'}
    return produce_success_response(response_data)


@csrf_exempt
def stop_test(request):
    test_id = int(request.GET.get('testId'))
    LoadTest.stop_test(test_id)
    response_data = {'status': 'stopped'}
    return produce_success_response(response_data)
