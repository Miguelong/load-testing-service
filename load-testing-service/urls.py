"""load-testing-service URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin
import views

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^load-test/setup/', views.setup, name='setup'),
    url(r'^load-test/updateTestCase/', views.update_test_case, name='updateTestCase'),
    url(r'^load-test/startTest/', views.start_test, name='startTest'),
    url(r'^load-test/getAllCases/', views.get_all_cases, name='getAllCases'),
    url(r'^load-test/getTestCase/', views.get_test_case, name='getTestCase'),
    url(r'^load-test/downloadReport/', views.download_report, name='downloadReport'),
    url(r'^load-test/stopTest/', views.stop_test, name='stopTest'),

]
