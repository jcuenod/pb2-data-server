#!/bin/sh

docker stop parabible-data-server
docker rm parabible-data-server
docker run --name parabible-data-server -e POSTGRES_PASSWORD=toor -e POSTGRES_DB=parabible -p 5432:5432 -d parabible/data:dev
docker logs -f parabible-data-server
