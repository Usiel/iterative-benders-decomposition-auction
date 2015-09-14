import math
from gurobipy.gurobipy import GRB, Model, quicksum, LinExpr
import itertools
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
        print 'phi %s' % (phi + secondTerm)

        # check if phi with current result of master-problem is z
        if math.fabs(phi + secondTerm + self.solver.z.x) < epsilon:
            self.printResults()
            return False
        # otherwise continue and add cut based on this iteration's allocation
        else:
            self.allocations.append(allocation)
            self.solver.addBendersCut(allocation, len(self.allocations))
            return True

    def printResults(self):
        for index, alloc in enumerate(self.allocations, start=1):
            print 'X%s:' % index,
            for assignment in alloc:
                print '%s <- ' % assignment.agentId,
                for item in assignment.items:
                    print '%s, ' % item,
            print ''



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
        self.m.addConstr(self.z, GRB.LESS_EQUAL, LinExpr(self.b, self.priceVars.values() + self.utilityVars.values()), name="X0")
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
            if l.Pi > 0:
                print('%s %g' % (l.constrName, l.Pi))

    # adds another cut z <= wb - ((c + wA)* X)
    def addBendersCut(self, allocation, name):
        #valuations summed up
        expr = LinExpr(self.b, self.priceVars.values() + self.utilityVars.values())
        for a in allocation:
            expr.addConstant(-a.valuation)
            expr.addTerms(-1, self.utilityVars[a.agentId])
            for item in a.items:
                expr.addTerms(-1, self.priceVars[item])

        self.m.addConstr(self.z, GRB.LESS_EQUAL, expr, name='X%s' % name)
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
        summedValuation = 0

        #as done in Nisan 200x
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
                for i in queryResponses[maximalPerItemValueAgentId][1]:
                    itemsPool = [item for item in itemsPool if item != i]
                agentsPool = [agent for agent in agentsPool if agent.id != maximalPerItemValueAgentId]
                allocation.append(Assignment(queryResponses[maximalPerItemValueAgentId][1], maximalPerItemValueAgentId, queryResponses[maximalPerItemValueAgentId][0]))
                summedValuation += queryResponses[maximalPerItemValueAgentId][0]
            else:
                break

        #check if assigning all items to one agent is better
        for agent in self.agents:
            valuation = agent.valueQuery(self.items[:])
            if valuation > summedValuation:
                summedValuation = valuation
                #allocation = [Assignment(self.items[:], agent.id, valuation)]


        for assignment in allocation:
            print '%s <- ' % assignment.agentId,
            for item in assignment.items:
                print '%s, ' % item,
        print ''

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

    def valueQuery(self, items):
        valuation = itertools.ifilter(lambda x: set(x[0]) == set(items), self.valuations).next()
        if valuation:
            return valuation[1]
        return 0


items = ["A", "B"]
agent1 = Agent(items, [(["A"], 6.), (["B"], 6.), (["A", "B"], 6.)], 1)
agent2 = Agent(items, [(["A"], 1.), (["B"], 1.), (["A", "B"], 5.)], 2)
agent3 = Agent(items, [(["A"], 3.), (["B"], 1.), (["A", "B"], 3.)], 3)
#items = ["A", "B", "C"]
#agent1 = Agent(items, [(["A"], 6.), (["B"], 6.), (["A", "B"], 6.), (["C"], 6.), (["A", "B", "C"], 6.), (["B", "C"], 6.)], 1)
#agent2 = Agent(items, [(["A"], 1.), (["B"], 1.), (["A", "B"], 4.), (["C"], 1.), (["A", "B", "C"], 10.), (["B", "C"], 2.)], 2)
#agent3 = Agent(items, [(["A"], 3.), (["B"], 1.), (["A", "B"], 3.), (["C"], 4.), (["A", "B", "C"], 15.), (["B", "C"], 4.)], 3)
agents = [agent1, agent2, agent3]
a = Auction(items, agents)

flag = True
while flag:
    flag = a.iterate()