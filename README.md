# Home Server Setup

Guide to set up a homeserver with various apps which will help you in the path of self hosting

## Hardware requirements

To start with a home server you don't need much of a budget. One can start of with a Raspberry Pi to start of. Most of your money is spent on storage compared to the server itself.

### My current setup

**HP Prodesk 600 G2 mini**
This is a mini PC which has tons of USB 3 ports and is cheap (Cheaper than a Raspberry pi but faster).

##### Specifications

- i5-6500T
- 16GB RAM
- 256GB Boot SSD
- 2X 1TB HDD (1 for storage and 1 for backups)

## Software side of things

You can install any operating system you feel comfortable with, I have decided to go with [Ubuntu Server](https://ubuntu.com/download/server). This is installed on the 256GB SSD and this makes things to boot up faster. If you are using a Pi then a PiOs Lite is better.

Make sure to have SSH enabled, so that it is easier to remote into the server. It is also recommended to have a static IP assigned to the server so it doesn't mess things up at a later point in time.

[Install docker](https://docs.docker.com/engine/install/) and make sure to the the user has sudo permissions.

I would recommend creating a folder named docker under your home folder so that you can store and mount all container configurations.

`mkdir ~/docker`

#### Self hosted Apps

1.  Portainer
2.  File browser
3.  Pi Hole with unbound
4.  Immich
5.  Duplicati
6.  Jellyfin
7.  qBitTorrent with OpenVPN
8.  Home Assistant

Lets start of with installing Portainer, with this you can run and manage all the containers from browser on your local network.
If you like to run everything via docker-compose then take a look at the respective folders.

### [Portainer](https://www.portainer.io/)

1. Create a container folder `mkdir ~/docker/portainer`
2. Create the container using the below docker run command

```
docker run -d \
    -p 9443:9443 \
    --name portainer \
    --restart always \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v ${HOME}/docker/portainer:/data \
    portainer/portainer-ce:latest
```

3. The application runs on HTTPS port 9443. https://{YOUR_SERVER_IP}:9443

### [File Browser](https://filebrowser.org/)

1. Create a container folder `mkdir ~/docker/filebrowser`
2. Create empty database file `touch ~/docker/filebrowser/filebrowser.db`
3. Create empty settings file `touch ~/docker/filebrowser/settings.json`
4. Create the container using the below docker run command

```
# Here /mnt is the Storage location, I have my HDD's mounted to /mnt. Replace accordingly

docker run -d --name fileBrowser\
    -v /mnt:/srv \
    -v ${HOME}/docker/filebrowser/filebrowser.db:/database/filebrowser.db \
    -v ${HOME}/docker/filebrowser/settings.json:/config/settings.json \
    -u $(id -u):$(id -g) \
    -p 8082:80 \
    filebrowser/filebrowser
```

5. The application runs on HTTP port 8082. http://{YOUR_SERVER_IP}:8082

### [Jellyfin](https://jellyfin.org/)

1. Create a container folder `mkdir ~/docker/jellyfin`
2. Create empty config directory `mkdir ~/docker/jellyfin/config`
3. Create empty cache directory `mkdir ~/docker/jellyfin/cache`
4. Create the container using the below docker run command

```
# Here {MEDIA LOCATION} is the Storage location, replace accordingly

docker run -d \
    --name jellyfin \
    --restart=unless-stopped \
    -u $(id -u):$(id -g) \
    -p 8096:8096 \
    -v ${HOME}/docker/jellyfin/config:/config \
    -v ${HOME}/docker/jellyfin/cache:/cache \
    -v {MEDIA LOCATION}:/media \
    --device /dev/dri/renderD128:/dev/dri/renderD128 \ #Optional If you have GPU this nees to be replaced
    jellyfin/jellyfin
```

5. The application runs on HTTP port 8096. http://{YOUR_SERVER_IP}:8096

### [Duplicati](https://www.duplicati.com/)

1. Create a container folder `mkdir ~/docker/duplicati`
2. Create a config folder `mkdir ~/docker/duplicati/config`
3. Create the container using the below docker run command

```
# Here {BACKUP_LOCATION} and {SOURCE_LOCATION} are the Storage location, replace accordingly

docker run -d \
    --name=duplicati \
    -u $(id -u):$(id -g) \
    -e TZ=Europe/Amsterdam \
    -p 8200:8200 \
    -v ${HOME}/docker/duplicati/config:/config \
    -v {BACKUP_LOCATION}:/backups \
    -v {SOURCE_LOCATION}:/source \
    --restart unless-stopped \
    lscr.io/linuxserver/duplicati:latest
```

4. The application runs on HTTP port 8200. http://{YOUR_SERVER_IP}:8200

### [qBitTorrent](https://github.com/MarkusMcNugen/docker-qBittorrentvpn) with OpenVpn

1. Create a container folder `mkdir ~/docker/qbittorrent`
2. Create a config folder `mkdir ~/docker/qbittorrent/config`
3. Place all OpenVPN config files inside the `config/openvpn` folder
4. Create the container using the below docker run command

```
# Here {DOWNLOAD_FOLDER} is the Storage location, replace accordingly

docker run --privileged  -d \
    --name=qbittorrent \
    -v ${HOME}/docker/qbittorrent/config:/config \
    -v {DOWNLOAD_FOLDER}:/downloads \
    -e "VPN_ENABLED=yes" \
    -e "VPN_USERNAME=VPN_USERNAME" \
    -e "VPN_PASSWORD=VPN_PASSWORD" \
    -e "LAN_NETWORK=192.168.1.0/24" \
    -e "NAME_SERVERS=8.8.8.8,8.8.4.4" \
    -p 8083:8080 \
    -p 8999:8999 \
    -p 8999:8999/udp \
    markusmcnugen/qbittorrentvpn
```

5. The application runs on HTTP port 8083. http://{YOUR_SERVER_IP}:8083

**NOTE:** If you get `Unauthorised` when you visit then navigate to `${HOME}/docker/qbittorrent/config/qBittorrent/config` and then edit the `qBittorrent.conf` file. Add `WebUI\HostHeaderValidation=false` to the end/along with other `WebUI\*` lines.
