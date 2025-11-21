#!/bin/bash
openssl req -x509 -newkey rsa:4096 -keyout ../src/key.pem -out ../src/cert.pem -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
