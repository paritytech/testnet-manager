# Dictionary to store SubstrateInterface Objects
# { network_name: SubstrateInterface Object }
# Why? the first query takes ~1 second because it pulls metadata from the network,
# the following queries are much faster, by reusing the connection we can speed up the process.
# todo: if we face a problem with the connection pool add a cron to clean it once an hour
# Note: because we use gunicorn each worker will have it own pool
network_connection_pool = {}
