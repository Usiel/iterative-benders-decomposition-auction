import math
from gurobipy.gurobipy import GRB, Model, quicksum, LinExpr
import itertools
import numpy as np

__author__ = 'Usiel'

epsilon = 0.0001


class Auction:
    def __init__(self, supply, agents):
        self.supply = supply
        self.agents = agents
        self.approximator = LaviSwamyGreedyApproximator(self.supply, self.agents)
        self.b = [(1. / self.approximator.gap) for i in range(0, len(self.agents))]
        self.b.append(self.supply / self.approximator.gap)
        self.solver = BendersSolver(self.b, self.agents)
        self.allocations = {'X0': []}

    def iterate(self):
        self.solver.optimize()
        allocation = self.approximator.approximate(self.solver.price, self.solver.utilities)
        first_term = sum([-w * b for w, b in zip(self.solver.utilities.values() + [self.solver.price], self.b)])
        second_term = 0
        for assignment in allocation:
            second_term += self.solver.price * assignment.quantity
            second_term += -self.solver.utilities[assignment.agent_id]
            second_term += assignment.valuation
        phi = first_term - second_term
        print 'phi = %s - %s = %s' % (first_term, second_term, phi)

        # check if phi with current result of master-problem is z
        if phi >= self.solver.z.x:
            self.print_results()
            return False
        # otherwise continue and add cut based on this iteration's allocation
        else:
            allocationName = 'X%s' % len(self.allocations)
            self.allocations[allocationName] = allocation
            self.solver.addBendersCut(allocation, allocationName)
            return True

    def print_results(self):
        for item in self.allocations.iteritems():
            print '%s (%s)' % (item[0], self.solver.m.getConstrByName(item[0]).pi)
            for assignment in item[1]:
                assignment.print_me()
            print ''


class BendersSolver:
    def __init__(self, b, agents):
        self.m = Model("master-problem")
        self.z = self.m.addVar(lb=-GRB.INFINITY, ub=GRB.INFINITY, name="z")
        self.b = b
        self.agents = agents

        self.price_var = dict()
        self.price_var = self.m.addVar(lb=-GRB.INFINITY, ub=0, name="price")
        self.utilityVars = dict()
        for agent in self.agents:
            self.utilityVars[agent.id] = self.m.addVar(lb=-GRB.INFINITY, ub=0, name="u_%s" % agent.id)

        self.m.update()

        # Initial constraints for empty allocation
        self.m.addConstr(self.z, GRB.LESS_EQUAL, LinExpr(self.b, self.utilityVars.values() + [self.price_var]),
                         name="X0")
        self.m.setObjective(self.z, GRB.MAXIMIZE)

    @property
    def price(self):
        return math.fabs(self.price_var.x)

    @property
    def utilities(self):
        return dict((v[0], math.fabs(v[1].x)) for v in self.utilityVars.iteritems())

    def optimize(self):
        self.m.optimize()
        for v in self.m.getVars():
            print('%s %g' % (v.varName, v.x))

        for l in self.m.getConstrs():
            if l.Pi > 0:
                print('%s %g' % (l.constrName, l.Pi))

    # adds another cut z <= wb - ((c + wA)* X)
    def addBendersCut(self, allocation, name):
        # valuations summed up
        expr = LinExpr(self.b, self.utilityVars.values() + [self.price_var])
        for a in allocation:
            expr.addConstant(-a.valuation)
            expr.addTerms(-1, self.utilityVars[a.agent_id])
            expr.addTerms(-a.quantity, self.price_var)

        self.m.addConstr(self.z, GRB.LESS_EQUAL, expr, name=name)
        # self.m.write("out.lp")


class LaviSwamyGreedyApproximator:
    def __init__(self, supply, agents):
        self.supply = supply
        self.agents = agents

    @property
    def gap(self):
        return 2.

    def approximate(self, price, utilities):
        left_supply = self.supply
        agents_pool = self.agents[:]
        allocation = []
        summed_valuations = 0

        # as done in Lavi & Swamy 2005
        while agents_pool and left_supply > 0:
            query_responses = dict()
            per_item_values = dict()
            for agent in agents_pool:
                demand = agent.query_demand(price, left_supply)
                if demand:
                    query_responses[agent.id] = demand
                    if (query_responses[agent.id].valuation - utilities[agent.id] - query_responses[agent.id].quantity * price) > 0:
                        per_item_values[agent.id] = (
                                                    query_responses[agent.id].valuation - utilities[agent.id] - price) / \
                                                    query_responses[agent.id].quantity
            if per_item_values:
                maximal_per_item_value_agent_id = max(per_item_values.iterkeys(),
                                                      key=(lambda key: per_item_values[key]))
                left_supply -= query_responses[maximal_per_item_value_agent_id].quantity
                agents_pool = [agent for agent in agents_pool if agent.id != maximal_per_item_value_agent_id]
                allocation.append(Assignment(query_responses[maximal_per_item_value_agent_id].quantity,
                                             maximal_per_item_value_agent_id,
                                             query_responses[maximal_per_item_value_agent_id].valuation))
                summed_valuations += query_responses[maximal_per_item_value_agent_id].valuation - utilities[
                    maximal_per_item_value_agent_id] - price * query_responses[maximal_per_item_value_agent_id].quantity
            else:
                break

        # check if assigning all items to one agent is better
        for agent in self.agents:
            valuation = agent.query_value(self.supply)
            if valuation.valuation - utilities[agent.id] - self.supply * price > summed_valuations:
                summed_valuations = valuation.valuation
                allocation = [Assignment(self.supply, agent.id, valuation.valuation)]

        for assignment in allocation:
            assignment.print_me()

        return allocation


class Assignment:
    def __init__(self, quantity, agent_id, valuation):
        self.quantity = quantity
        self.agent_id = agent_id
        self.valuation = valuation

    def print_me(self):
        print 'Agent %s receives %s item(s)' % (self.agent_id, self.quantity)


class Valuation:
    def __init__(self, quantity, valuation):
        self.quantity = quantity
        self.valuation = valuation


class Agent:
    def __init__(self, valuations, id):
        self.id = id
        self.valuations = valuations

    def query_demand(self, price, left_supply):
        best_valuation = None
        best_value_per_item = None
        for valuation in self.valuations:
            if valuation.quantity <= left_supply:
                value_per_item = (valuation.valuation - valuation.quantity * price) / valuation.quantity
                if value_per_item > 0. and value_per_item > best_value_per_item:
                    best_valuation = valuation
                    best_value_per_item = value_per_item
        return best_valuation

    def query_value(self, quantity):
        valuation = itertools.ifilter(lambda x: x.quantity == quantity, self.valuations).next()
        if valuation:
            return valuation
        return None


agent1 = Agent([Valuation(1, 6.), Valuation(2, 6.), Valuation(3, 6.), Valuation(4, 6.)], 1)
agent2 = Agent([Valuation(1, 1.), Valuation(2, 4.), Valuation(3, 4.), Valuation(4, 6.)], 2)
agent3 = Agent([Valuation(1, 0.), Valuation(2, 1.), Valuation(3, 1.), Valuation(4, 1.)], 3)
agents = [agent1, agent2, agent3]
a = Auction(4, agents)

flag = True
while flag:
    flag = a.iterate()
