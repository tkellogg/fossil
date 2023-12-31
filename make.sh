#!/bin/bash

function update_deps() {
    curl 'https://unpkg.com/htmx.org@latest' -o app/public/htmx.js
}

function run() {
    poetry run uvicorn --host 0.0.0.0 --port 8888 --reload fossil.server:app
}


$1 "$@"
