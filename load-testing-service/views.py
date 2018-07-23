import json
import os

import MySQLdb
import matplotlib
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from LoadTest import *

matplotlib.use('Agg')
from django.http import FileResponse

running_tests = {}
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'temp')


def produce_success_response(data):
    response_body = {}
    response_body['meta'] = {'code': 200}
    response_body['data'] = data
    return HttpResponse(json.dumps(response_body), content_type="application/json")


def produce_fail_response(data):
    response_body = {}
    response_body['meta'] = {'code': 500}
    response_body['data'] = data
    return HttpResponse(json.dumps(response_body), content_type="application/json")


@csrf_exempt
def setup(request):
    user = request.POST.get('user')
    testName = request.POST.get('testName')

    url = request.POST.get('apiUrl')
    # print url
    concurrentNum = int(request.POST.get('concurrentNum'))
    # print concurrentNum
    method = request.POST.get('apiMethod')
    # print method
    header = request.POST.get('apiHeader', '')
    # print header
    payload = request.POST.get('apiPayload', '')
    # print payload
    timeout = int(request.POST.get('apiTimeout'))
    # print timeout
    proxy = request.POST.get('apiProxy', '')
    # print proxy
    parameters = request.FILES.get('parameters')
    # print parameters.size,parameters.name

    db = MySQLdb.connect("10.100.17.151", "demo", "RE3u6pc8ZYx1c", "test")
    cursor = db.cursor()
    insertSql="insert load_test (user,testName,apiUrl,concurrentNum,apiMethod,apiHeader,apiPayload,apiTimeout,apiProxy, parameters)" \
              " values('%s', '%s', '%s', '%d', '%s', '%s', '%s', '%d', '%s', '%s')" % \
              (user, testName, url, concurrentNum, method, header, payload, timeout, proxy, MySQLdb.Binary(parameters.read()))

    try:
        cursor.execute(insertSql)
        test_id = int(db.insert_id())
        print test_id
        db.commit()

    except Exception, e:
        errMessage = repr(e)
        print errMessage
        db.rollback()

    db.close()

    response_data = {}

    if test_id is None:
        response_data['errMessage'] = errMessage
        return produce_fail_response(response_data)
    else:
        response_data['testId'] = test_id
        return produce_success_response(response_data)


@csrf_exempt
def get_all_cases(request):
    data = json.loads(request.body)
    page = int(data.get('pagination').get('page'))
    perPage = int(data.get('pagination').get('perPage'))
    start = perPage*(page-1)
    print start

    db = MySQLdb.connect("10.100.17.151", "demo", "RE3u6pc8ZYx1c", "test")
    cursor = db.cursor()

    cursor.execute("select count(*) from load_test")
    res = cursor.fetchone()
    totalSize= int(res[0])

    sql = "select id,user,testName,status,progress from load_test order by id limit "+str(start)+","+str(perPage)
    cursor.execute(sql)
    results = cursor.fetchall()
    response_data={}
    list=[]
    for row in results:
        id=row[0]
        user=row[1]
        testName=row[2]
        status=row[3]
        progress=row[4]
        list.append({"testId": id, "user": user, "testName": testName, "status": status, "progress": progress})

    response_data={"list": list, "pagination": {"totalSize": totalSize}}

    db.close()
    return produce_success_response(response_data)


@csrf_exempt
def download_report(request):
    test_id = request.GET.get('testId')
    db = MySQLdb.connect("10.100.17.151", "demo", "RE3u6pc8ZYx1c", "test")
    cursor = db.cursor()
    cursor.execute("select report from load_test where id="+str(test_id))
    res=cursor.fetchone()
    report=res[0]

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
    db = MySQLdb.connect("10.100.17.151", "demo", "RE3u6pc8ZYx1c", "test")
    cursor = db.cursor()
    try:
        cursor.execute("select status from load_test where id="+str(test_id))
        res = cursor.fetchone()
        status = res[0]
        # if the test is already running leave it
        if status == 'running':
            response_data = {'error': 'The test case is already running.\nPlease wait until it is completed.'}
            return produce_fail_response(response_data)

        cursor.execute("update load_test set progress=0.0, status='running' where id="+str(test_id))
        db.commit()
    except Exception, e:
        print repr(e)
        db.rollback()
        response_data = {'stage': 'update status', 'error': repr(e)}
        return produce_fail_response(response_data)

    # get configuration of the test
    sql = "select apiUrl,concurrentNum,apiMethod,apiHeader,apiPayload,apiTimeout,apiProxy,parameters,report " \
          "from load_test where id="+str(test_id)
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

    db.close()

    # delete report and images of last test
    print report
    if report is not None and report != '':
        prefix = report.split('.')[0]
        success_img = prefix + '_Success.png'
        timeout_img = prefix + '_Timeout.png'
        try:
            os.remove(os.path.join(TEMP_DIR, report))
            os.remove(os.path.join(TEMP_DIR, success_img))
            os.remove(os.path.join(TEMP_DIR, timeout_img))
        except Exception, e:
            print repr(e)

    # parameters_list is a list of parameters that the get or post request requires
    lines = parameters.split('\n')
    parameters_list = []
    for line in lines:
        if line != '':
            parameters_list.append(line)

    # set to None of empty parameters
    if header == '':
        header = None

    if payload == '':
        payload = None

    if proxy == '':
        proxy = None

    # start the load test
    test = LoadTest(url, concurrent_num, method, header, payload, timeout, proxy, parameters_list, test_id)
    test.startTest()

    # put the reference of the object into a global dictionary
    # the reference is used in case of user want to stop the load test
    # running_tests[test_id] = test

    response_data = {'status': 'running'}
    return produce_success_response(response_data)


@csrf_exempt
def stop_test(request):
    test_id = int(request.GET.get('testId'))
    # test = running_tests[test_id]
    # test.stopTest()
    LoadTest.stop_test(test_id)
    response_data = {'status': 'stopped'}
    return produce_success_response(response_data)
