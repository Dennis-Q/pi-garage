docker container run -dit -v `pwd`/data:/app/data --restart always --name pi-garage --network=pi-net --ip=172.18.0.2 -t pi-garage:v0.4
