import math
from gurobipy.gurobipy import GRB, Model, quicksum, LinExpr
import numpy as np

__author__ = 'Usiel'

epsilon = 0.0001

class Auction:
    def __init__(self, items, agents):
        self.items = items
        self.agents = agents
        self.approximator = NisanDemandQueryApproximator(self.items, self.agents)
        self.b = [(1./self.approximator.gap) for i in range(0, len(self.items) + len(self.agents))]
        self.solver = BendersSolver(self.b, self.items, self.agents)
        self.allocations = []

#    @property
#    def prices(self):
#        return self.w[1:len(self.items)+1]

#    @property
#    def utilities(self):
#        return self.w[len(self.items)-1:]

    def iterate(self):
        self.solver.optimize()
        allocation = self.approximator.approximate(self.solver.prices, self.solver.utilities)
        phi = sum([(-1)*w*b for w,b in zip(self.solver.prices.values() + self.solver.utilities.values(), self.b)])
        secondTerm = 0
        for assignment in allocation:
            #assignment[0] = items
            #assignment[1][0] = agent.id
            #assignment[1][1] = v_i(item)
            for item in assignment.items:
                secondTerm += self.solver.prices[item]
            secondTerm += self.solver.utilities[assignment.agentId]
            secondTerm -= assignment.valuation
        print('phi %s' % -(phi + secondTerm))
        if -(phi + secondTerm) - self.solver.z.x < epsilon:
            return False
        else:
            self.allocations.append(allocation)
            self.solver.addBendersCut(allocation)
            return True



class BendersSolver:
    def __init__(self, b, items, agents):
        self.m = Model("master-problem")
        self.z = self.m.addVar(lb=-GRB.INFINITY, ub=GRB.INFINITY, name="z")
        self.b = b
        self.items = items
        self.agents = agents

        self.priceVars = dict()
        for item in self.items:
            self.priceVars[item] = self.m.addVar(lb=-GRB.INFINITY, ub=0, name="p_%s" % item)
        self.utilityVars = dict()
        for agent in self.agents:
            self.utilityVars[agent.id] = self.m.addVar(lb=-GRB.INFINITY, ub=0, name="u_%s" % agent.id)

        self.m.update()

        #Initial constraints for empty allocation
        self.m.addConstr(self.z, GRB.LESS_EQUAL, LinExpr(self.b, self.priceVars.values() + self.utilityVars.values()))
        self.m.setObjective(self.z, GRB.MAXIMIZE)

    @property
    def prices(self):
        return dict((v[0], v[1].x) for v in self.priceVars.iteritems())

    @property
    def utilities(self):
        return dict((v[0], v[1].x) for v in self.utilityVars.iteritems())

    def optimize(self):
        #self.m.update()
        self.m.optimize()
        for v in self.m.getVars():
            print('%s %g' % (v.varName, v.x))

        for l in self.m.getConstrs():
            print('%s %g' % (l.constrName, l.Pi))

    def addBendersCut(self, allocation):
        #valuations summed up
        expr = LinExpr(self.b, self.priceVars.values() + self.utilityVars.values())
        for a in allocation:
            expr.addConstant(-a.valuation)
            expr.addTerms(-1, self.utilityVars[a.agentId])
            for item in a.items:
                expr.addTerms(-1, self.priceVars[item])

        self.m.addConstr(self.z, GRB.LESS_EQUAL, expr)
        #self.m.write("out.lp")

class NisanDemandQueryApproximator:
    def __init__(self, items, agents):
        self.items = items
        self.agents = agents

    @property
    def gap(self):
        return min(len(self.agents), 4*math.sqrt(len(self.items)))

    def approximate(self, prices, utilities):
        itemsPool = self.items[:]
        agentsPool = self.agents[:]
        allocation = []

        while itemsPool and agentsPool:
            queryResponses = dict()
            perItemValues = dict()
            for agent in agentsPool:
                demand = agent.queryDemand(prices, itemsPool[:])
                if demand:
                    queryResponses[agent.id] = demand
                    price = sum([prices[item] for item in demand[1]])
                    if ((queryResponses[agent.id][0] + utilities[agent.id] + price)) > 0:
                        perItemValues[agent.id] = (queryResponses[agent.id][0] + utilities[agent.id] + price)/len(queryResponses[agent.id][1])
            if perItemValues:
                maximalPerItemValueAgentId = max(perItemValues.iterkeys(), key=(lambda key: perItemValues[key]))
                for item in queryResponses[agent.id][1]:
                    itemsPool.remove(item)
                agentsPool = [agent for agent in agentsPool if agent.id != maximalPerItemValueAgentId]
                allocation.append(Assignment(queryResponses[maximalPerItemValueAgentId][1], maximalPerItemValueAgentId, queryResponses[maximalPerItemValueAgentId][0]))
                print("Item(s) %s to Agent %s with valuation %s" % (queryResponses[maximalPerItemValueAgentId][1], maximalPerItemValueAgentId, queryResponses[maximalPerItemValueAgentId][0]))
            else:
                break

        return allocation

class Assignment:
    def __init__(self, items, agentId, valuation):
        self.items = items
        self.agentId = agentId
        self.valuation = valuation

class Agent:
    def __init__(self, items, valuations, id):
        self.id = id
        self.valuations = valuations

    def queryDemand(self, prices, items):
        bestItemSet = None
        bestValuePerItem = None
        for valuation in self.valuations:
            if all(item in items for item in valuation[0]):
                valuePerItem = (valuation[1] + sum([prices[i] for i in valuation[0]]))/len(valuation[0])
                if valuePerItem > bestValuePerItem:
                    bestItemSet = (valuation[1], valuation[0])
                    bestValuePerItem = valuePerItem
        return bestItemSet

items = ["A", "B"]
agent1 = Agent(items, [(["A"], 6.), (["B"], 6.), (["A", "B"], 6.)], 1)
agent2 = Agent(items, [(["A"], 1.), (["B"], 1.), (["A", "B"], 5.)], 2)
agent3 = Agent(items, [(["A"], 3.), (["B"], 1.), (["A", "B"], 3.)], 3)
agents = [agent1, agent2, agent3]
a = Auction(items, agents)

flag = True
while flag:
    flag = a.iterate()