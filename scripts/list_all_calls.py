#!/usr/bin/env python3

from substrateinterface import SubstrateInterface


substrate = SubstrateInterface("ws://localhost:9944")

constants = substrate.get_metadata_constants()
extrinsics = substrate.get_metadata_call_functions()
chainstate = substrate.get_metadata_storage_functions()
rpc = substrate.rpc_request(method="rpc_methods", params=[])

result_constants = []
for c in constants:
    #print(c)
    result_constants.append("{}.{}\t{}".format(c['module_name'], c['constant_name'], c['documentation'].split("\n")[0]))

result_extrinsics = []
for e in extrinsics:
    #print(e)
    result_extrinsics.append("{}.{}\t{}".format(e['module_name'], e['call_name'], e['documentation'].split("\n")[0]))

result_chainstate = []
for e in chainstate:
    #print(e)
    result_chainstate.append("{}.{}\t{}".format(e['module_name'], e['storage_name'], e['documentation'].split("\n")[0]))

print("Constants:\n{}".format("\n".join(sorted(result_constants))))
print("Extrinsics:\n{}".format("\n".join(sorted(result_extrinsics))))
print("Chainstate:\n{}".format("\n".join(sorted(result_chainstate))))
print("RPC call:\n{}".format("\n".join(sorted(rpc['result']['methods']))))

