# pi-garage
Controlling a garage door through relays &amp; mqtt (for integration with HomeAssistant)

Based on the work of Nickduino / Pi-Somfy
https://github.com/Nickduino/Pi-Somfy

There are two ways to run 'Pi-Garage':
1. Regular way (python3 on raspbian as pi-user)
2. Within docker (and using the hosts pigpiod-service)

## Regular way
In case you run into errors with dependencies, please check the Pi-Somfy-readme which this project is based on.

### Copy pi-garage.service & start service
Copy the pi-garage.service from this project to your user homefolder in '.config/systemd/user/', e.g.:
/home/pi/.config/systemd/user/pi-garage.service

You might want to edit the paths if they differ from mine.

Then you might have to reload systemd (user):

`systemctl --user daemon-reload`

If you want to start the service on boot, run as root:

`loginctl enable-linger <user>`

Then also enable the service (and start it if you like):
```
systemctl --user enable pi-garage
systemctl --user start pi-garage
```

## Docker-way:
First, install docker-ce (preferably via the script).

### Create user defined network called 'pi-net' using dockernetwork.command-file

`bash dockernetwork.command`
### Build docker-image using dockerbuild.command-file 
`bash dockerbuild.command`
### Modify pigpiod-service to only listen to localhost and the docker ip-address

`sudo systemctl edit pigpiod`
```
[Service]
ExecStart=
ExecStart=/usr/bin/pigpiod -n localhost -n 172.18.0.2
```
then daemon-reload systemd and restart the service:
```
sudo systemctl daemon-reload
sudo systemctl restart pigpiod
```
Afterwards, you can check using `ps -ef` if the service is running with the correct arguments.

### Start the container using the dockerrun.command-file (only the first time)

`bash dockerrun.command`

If there is no 'operateGarage.conf' yet, it will be created in the data-folder. You can modify the related GPIO-settings according to your setup.
