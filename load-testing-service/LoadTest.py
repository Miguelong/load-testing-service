#!/usr/bin/python
# -*- coding: UTF-8 -*-

import Queue
import json
import os
import threading
import time

import MySQLdb
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Pt


class LoadTest:
    # temp dir where generated report and images are placed
    TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'temp')

    # store the stop flags of tests
    STOP_SETTING = {}

    def __init__(self, url, concurrent_num, method, header, payload, timeout, proxy, parameters_list, test_id):
        self.url = url
        self.concurrent_num = concurrent_num
        self.method = method
        self.header = header
        self.payload = payload
        self.timeout = timeout
        self.proxy = proxy
        self.parameters_list = parameters_list
        self.test_id = test_id
        # load test begins
        self.begin_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        # tmsp is used in the file names
        self.tmsp = time.strftime("%Y%m%d%H%M%S", time.localtime())
        # self.stop = False
        self.STOP_SETTING[test_id] = False


    def statistic(self, title, queue, document):
        dict = {}
        sum = 0.0
        count = 0
        max = 0.0
        min = 100.0
        data = []
        if queue.empty():
            return

        document.add_heading(title + ': ' + str(queue.qsize()), 2)

        while not queue.empty():
            total_seconds = round(queue.get(), 2)
            data.append(total_seconds)
            if dict.has_key(total_seconds):
                dict[total_seconds] = dict[total_seconds] + 1
            else:
                dict[total_seconds] = 1

            if total_seconds > max:
                max = total_seconds

            if total_seconds < min:
                min = total_seconds

            sum += total_seconds
            count = count + 1

        average = round(sum / count, 3)

        items = dict.items()
        items.sort()

        bins = int((max - min) / 0.01)
        if bins == 0:
            bins = 1

        plt.hist(data, bins=bins, color='steelblue', edgecolor='k', label='title')
        plt.title(title)
        plt.xlabel('Response time (s)')
        plt.ylabel('Count')

        img = str(self.test_id) + "_" + self.tmsp + '_' + title + ".png"
        plt.savefig(os.path.join(self.TEMP_DIR, img))

        document.add_picture(os.path.join(self.TEMP_DIR, img))
        paragraph = document.add_paragraph('')
        run = paragraph.add_run('max:' + str(max) + ' min:' + str(min) + ' average:' + str(average) + '\n\n')
        run.font.size = Pt(12)

        left_bound = min
        right_bound = min + 0.5
        interval_count = 0
        detail = ""
        run = paragraph.add_run('[' + str(left_bound) + ',' + str(right_bound) + '): ')
        run.font.size = Pt(12)
        for item in items:
            total_seconds = item[0]
            count = item[1]
            while total_seconds >= right_bound:
                left_bound = right_bound
                right_bound = right_bound + 0.5
                if total_seconds < right_bound:
                    if len(detail) > 0:
                        detail = detail[0:len(detail) - 1]
                    run = paragraph.add_run(str(interval_count)+'\n')
                    run.font.size = Pt(12)
                    run = paragraph.add_run(detail + '\n\n')
                    run.font.size = Pt(12)
                    run = paragraph.add_run('[' + str(left_bound) + ',' + str(right_bound) + '): ')
                    run.font.size = Pt(12)
                    interval_count = 0
                    detail = ""

            detail = detail + "(" + str(total_seconds) + "," + str(count) + "),"
            interval_count = interval_count + count

        if len(detail) > 0:
            detail = detail[0:len(detail) - 1]
            run = paragraph.add_run(str(interval_count) + '\n' + detail + '\n')
            run.font.size = Pt(12)

    def outputFails(self, queue, document):
        paragraph = document.add_paragraph('')

        if not queue.empty():
            # print >> file, "------------------------------------------------------------------------------------"
            # print >> file, "Fail: ", queue.qsize()
            run = paragraph.add_run('total:' + str(queue.qsize()))
            run.font.size = Pt(12)

        dict = {}
        while not queue.empty():
            item = queue.get()
            key = item[0]
            value = item[1]
            if dict.has_key(key):
                dict[key].append(value)
            else:
                dict[key] = [value]

        items = dict.items()
        for item in items:
            # print >> file, item[0]
            document.add_heading(item[0], 2)
            # print >> file, item[1]
            paragraph = document.add_paragraph('')
            run = paragraph.add_run('total:' + str(len(item[1])) + '\n')
            run.font.size = Pt(12)
            run = paragraph.add_run(item[1])
            run.font.size = Pt(12)
            run = paragraph.add_run('\n\n')
            run.font.size = Pt(12)

    def request_get(self, url):
        try:
            # r = requests.get(url, timeout=timeout)
            r = requests.get(url)
            json = r.json()
            code = json['meta']['code']
            total_seconds = r.elapsed.total_seconds()
            return (None, code, total_seconds)
        except Exception, e:
            return (e, None, None)

    def request_post(self, url, payload):
        try:
            # r = requests.post(url, json=payload, timeout=timeout)
            r = requests.post(url, json=payload)
            json = r.json()
            code = json['meta']['code']
            total_seconds = r.elapsed.total_seconds()
            return (None, code, total_seconds)
        except Exception, e:
            return (e, None, None)

    def request_get_proxy(self, url):
        try:
            if self.header is None:
                cmd = "curl -w 'time_total: %{time_total}\n' '" + url + "' -H 'Content-Type:application/json' --proxy " + self.proxy
            else:
                cmd = "curl -w 'time_total: %{time_total}\n' '" + url + "' -H 'Content-Type:application/json' -H '" + self.header + "' --proxy " + self.proxy

            res = os.popen(cmd).read()
            index = res.find('time_total')
            code = json.loads(res[0:index])['meta']['code']
            total_seconds = float(res[index + 12:].replace("\n", ""))
            return (None, code, total_seconds)
        except Exception, e:
            return (e, None, None)

    def request_post_proxy(self, url, payload):
        try:
            if self.header is None:
                cmd = "curl -w 'time_total: %{time_total}\n' '" + url + "' -X POST -H 'Content-Type:application/json' -d '" + payload + "' --proxy " + self.proxy
            else:
                cmd = "curl -w 'time_total: %{time_total}\n' '" + url + "' -X POST -H 'Content-Type:application/json' -H '" + self.header + "' -d '" + payload + "' --proxy " + self.proxy

            res = os.popen(cmd).read()
            index = res.find('time_total')
            code = json.loads(res[0:index])['meta']['code']
            total_seconds = float(res[index + 12:].replace("\n", ""))
            return (None, code, total_seconds)
        except Exception, e:
            return (e, None, None)

    def processResponse(self, res, timeout, successQueue, timeoutQueue, failQueue, parameters):
        e = res[0]
        code = res[1]
        total_seconds = res[2]
        if e is None:
            if code == 200:
                if total_seconds > timeout:
                    timeoutQueue.put(total_seconds)
                else:
                    successQueue.put(total_seconds)
            else:
                failQueue.put(("code " + str(code), parameters))
        else:
            failQueue.put((repr(e), parameters))

    def testGet(self, url_template, timeout, successQueue, timeoutQueue, failQueue, parametersList):
        # get count of parameters of the url
        parameters_count = url_template.count('${')
        for parameters in parametersList:
            # in case of user stop the test
            # if self.stop:
            if self.STOP_SETTING[self.test_id]:
                break

            list = json.loads(parameters)
            url = url_template
            for i in range(parameters_count):
                old = '${' + str(i) + '}'
                new = list[i]
                url = url.replace(old, new)
            if self.proxy is None:
                res = self.request_get(url)
            else:
                res = self.request_get_proxy(url)
            self.processResponse(res, timeout, successQueue, timeoutQueue, failQueue, parameters)

    def testPost(self, url, payload_template, timeout, successQueue, timeoutQueue, failQueue, parametersList):
        # get count of parameters of the payload
        parameters_count = payload_template.count('${')
        for parameters in parametersList:
            # in case of user stop the test
            # if self.stop:
            if self.STOP_SETTING[self.test_id]:
                break

            list = json.loads(parameters)
            payload = payload_template
            for i in range(parameters_count):
                old = '${' + str(i) + '}'
                new = list[i]
                payload = payload.replace(old, new)

            if self.proxy is None:
                res = self.request_post(url, json.loads(payload))
            else:
                res = self.request_post_proxy(url, payload)

            self.processResponse(res, timeout, successQueue, timeoutQueue, failQueue, parameters)

    def getProgress(self, total_num, successQueue, timeoutQueue, failQueue):
        db = MySQLdb.connect("10.100.17.151", "demo", "RE3u6pc8ZYx1c", "test")
        cursor = db.cursor()

        progress = 0.0
        while progress < 100.0:
            # in case of user stop the test
            # if self.stop:
            if self.STOP_SETTING[self.test_id]:
                break

            time.sleep(3)
            processed_num = successQueue.qsize() + timeoutQueue.qsize() + failQueue.qsize()
            progress = float(processed_num) / total_num * 100
            print total_num, processed_num
            print progress
            try:
                cursor.execute("update load_test set progress=" + str(progress) + " where id=" + str(self.test_id))
                db.commit()
            except Exception, e:
                print repr(e)
                db.rollback()


        if progress == 100.0:
            status = 'completed'
        else:
            status = 'stopped'

        try:
            cursor.execute("update load_test set progress="+str(progress)+", status='"+status+"' where id=" + str(self.test_id))
            db.commit()
        except Exception, e:
            print repr(e)
            db.rollback()

        db.close()

        self.getResult(successQueue, timeoutQueue, failQueue)

    def getResult(self, successQueue, timeoutQueue, failQueue,):
        end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        document = Document()

        document.add_heading('Report', 0)
        paragraph = document.add_paragraph('')
        run = paragraph.add_run('begin: ' + self.begin_time + '\n')
        run.font.size = Pt(12)
        run = paragraph.add_run('end: ' + end_time)
        run.font.size = Pt(12)

        document.add_heading('Testing Parameters', 1)
        paragraph = document.add_paragraph('')
        run = paragraph.add_run('Concurrent threads: ' + str(self.concurrent_num) + '\n')
        run.font.size = Pt(12)
        run = paragraph.add_run('Url: ' + self.url + '\n')
        run.font.size = Pt(12)
        if self.payload is not None:
            run = paragraph.add_run('Payload: ' + self.payload + '\n')
            run.font.size = Pt(12)
        if self.header is not None:
            run = paragraph.add_run('Header: ' + self.header + '\n')
            run.font.size = Pt(12)
        if self.proxy is not None:
            run = paragraph.add_run('Proxy: ' + self.proxy + '\n')
            run.font.size = Pt(12)

        document.add_heading('Statistics', 1)

        self.statistic('Success', successQueue, document)
        self.statistic('Timeout', timeoutQueue, document)

        document.add_heading('Fail ', 1)
        self.outputFails(failQueue, document)

        # print >> result

        # print >> result, "end:", end_time

        # result.close()
        doc = str(self.test_id) + '_' + self.tmsp + '.docx'
        document.save(os.path.join(self.TEMP_DIR, doc))


        db = MySQLdb.connect("10.100.17.151", "demo", "RE3u6pc8ZYx1c", "test")
        cursor = db.cursor()
        sql = "update load_test set report='%s' where id='%s'" % \
              (doc, str(self.test_id))

        try:
            cursor.execute(sql)
            db.commit()
        except Exception,e:
            print repr(e)
            db.rollback()

        db.close()


    def startTest(self):
        # result = open("result_" + str(self.concurrent_num) + "_" + self.tmsp + ".txt", 'w+')

        # print >> result, "Concurrent threads:", str(self.concurrent_num)
        # print >> result, "Url:", self.url
        # print >> result, "Method:", self.method
        # if self.proxy is not None:
        #     print >> result, "Proxy:", self.proxy
        # if self.header is not None:
        #     print >> result, "Header:", self.header
        # print >> result
        #
        # print >> result, "begin:", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        # print >> result

        ##split parameters for each thread
        parameters = []
        total_num = len(self.parameters_list)
        size = total_num / self.concurrent_num
        begin = 0
        end = size
        for i in range(self.concurrent_num):
            if i == self.concurrent_num - 1:
                end = total_num

            arr = self.parameters_list[begin:end]
            parameters.append(arr)
            begin = begin + size
            end = end + size

        successQueue = Queue.Queue(total_num)
        timeoutQueue = Queue.Queue(total_num)
        failQueue = Queue.Queue(total_num)
        threads = []
        for i in range(self.concurrent_num):
            parametersPerThread = parameters[i]
            if self.method == 'get':
                t = threading.Thread(target=self.testGet, args=(
                self.url, self.timeout, successQueue, timeoutQueue, failQueue, parametersPerThread,))
            elif self.method == 'post':
                t = threading.Thread(target=self.testPost, args=(
                self.url, self.payload, self.timeout, successQueue, timeoutQueue, failQueue, parametersPerThread,))

            t.setDaemon(True)
            t.start()
            threads.append(t)

        t = threading.Thread(target=self.getProgress, args=(total_num, successQueue, timeoutQueue, failQueue,))
        t.setDaemon(True)
        t.start()
        threads.append(t)

    @classmethod
    def stop_test(cls, test_id):
        cls.STOP_SETTING[test_id] = True
