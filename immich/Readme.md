### [Immich](https://immich.app/)

1. Create a container folder `mkdir ~/docker/immich`
2. `cd` to the immich directory (`cd ~/docker/immich`)
3. Fetch the `docker-compose.yaml` using
   `wget https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml`
4. Fetch the `.env` file using
   `wget -O .env https://github.com/immich-app/immich/releases/latest/download/example.env`
5. Update the `.env` file with new passwords (`nano .env`)
6. If you have a GPU the you can fetch and update `hwaccel.yml` using
   `wget https://github.com/immich-app/immich/releases/latest/download/hwaccel.yml `
7. Run `docker-compose up -d` to get the containers up and running
8. The application runs on HTTP port 2283. http://{YOUR_SERVER_IP}:2283

[Detailed documentation](https://immich.app/docs/install/docker-compose)

#### Upgrading

1. Always make sure to read the release notes to make sure there are no breaking changes
2. Navigate to Immich directory using `cd ~/docker/immich`
3. Run `docker-compose pull && docker-compose up -d`

#### Bulk upload from a folder

1. Navigate to the directory having all the photos or videos
2. Run the below command after replacing respective `API_KEY` and `SERVER_IP`

```
docker run -it --rm -v "$(pwd):/import" ghcr.io/immich-app/immich-cli:latest upload --recursive --key {API_KEY} --server http://SERVER_IP:2283/api
```
