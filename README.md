
How to run server?
1. first ssh to azkaban:
#>sshazk

2. switch to root
#>sudo su - root

3. enter the folder
cd /var/applications/load-testing-service


4. runserver
nohup python manage.py runserver 0.0.0.0:8002 > django.log 2>&1 &