#!/usr/bin/env python

import networkx as nx
from flock_simulator.msg import FlockState, FlockCommand

# TODO Implement duckie initial(t=0) status = 'IDLE'


class Dispatcher(object):
    def __init__(self, skeleton_graph):
        self.skeleton_graph = skeleton_graph

        # Commands
        self.commands = []

    def update(self, state):
        # EXAMPLE FOR STATE:
        # state = {
        #   'duckies': [
        #       'duckie-0': {
        #           'status': 'IDLE',
        #           'lane': 'l001',
        #       },
        #       'duckie-1': {
        #           'status': 'IDLE',
        #           'lane': 'l042',
        #       }, ...
        #   ]
        #   'requests': [
        #       {
        #           'time': [time of request],
        #           'duckie_id': [duckie which is serving the request (empty if unassigned)],
        #           'start_node': [start node of graph (networkx)],
        #           'end_node': [end node of graph (networkx)],
        #       }, ...
        #   ]
        # }

        duckies = state['duckies']
        requests = state['requests']
        paths = []

        # Get open requests
        open_requests = []
        for request in requests:
            if not request['duckie_id']:
                open_requests.append(request)

        # check if there are requests
        if open_requests:

            # Update duckiestatus
            for duckie_id in duckies:
                if not open_requests:
                    break

                duckie = duckies[duckie_id]
                if duckie['status'] != 'IDLE':
                    continue

                current_node = self.node(
                    duckie['lane'])  # Node the duckie is heading to

                # find closest open request
                closest_request = next(iter(open_requests), None)
                request_index = 0
                closest_request_index = 0
                for open_request in open_requests:
                    if self.dist(current_node, open_request) < self.dist(
                            current_node, closest_request):
                        closest_request = open_request
                        closest_request_index = request_index
                    request_index += 1

                start_node = closest_request['start_node']

                # generate path and assign
                path_pair = self.generatePathPair(
                    duckie_id, closest_request_index, current_node, start_node)
                paths.append(path_pair)

        # generateCommands from path
        # EXAMPLE FOR PATHS:
        # paths = [
        #   {
        #       'duckie_id': 'duckie-0',
        #       'request_index': 2,
        #       'path': [list of nodes]
        #   },
        #   {
        #       'duckie_id': 'duckie-1',
        #       'request_index': 0,
        #       'path': [list of nodes]
        #   }, ...
        # ]

        self.commands = self.generateCommands(paths)

    def generateCommands(self, paths):
        commands = []
        for path in paths:
            command = {
                'duckie_id': path['duckie_id'],
                'request_index': path['request_index'],
                'goal_node': path['path'][0]
            }
            commands.append(command)
        return commands

    def getClosestRequest(self, open_requests, node):
        if not open_requests:  # if no open requests
            return
        closest_request = open_requests.keys()[0]
        for open_request in open_requests:
            if self.dist(node, open_request) < self.dist(
                    node, closest_request):
                closest_request = open_request

        return closest_request

    def dist(self, node, request):
        # generate dijkstra_distance (closest)
        return nx.dijkstra_path_length(self.skeleton_graph.G, node,
                                       request['start_node'])

    # generate dijkstra_path
    def generatePathPair(self, duckie_id, request_index, current_node,
                         goal_node):
        path = {}
        path['duckie_id'] = duckie_id
        path['request_index'] = request_index
        path['path'] = nx.dijkstra_path(self.skeleton_graph.G, current_node,
                                        goal_node)
        return path

    def node(self, lane):
        # Get end node of lane
        edges = list(self.skeleton_graph.G.edges(data=True))
        edge_data = [edge for edge in edges if edge[2]['lane'] == lane]
        return edge_data[0][1]
