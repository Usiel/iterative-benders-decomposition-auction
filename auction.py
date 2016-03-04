import copy
import math
import pprint
import itertools

from gurobipy.gurobipy import Model, GRB, quicksum, LinExpr

from agent import generate_randomized_agents, ManualAgent
from common import epsilon, Valuation, ConsoleLogger, BlackHoleLogger
from solver import BendersSolver, LaviSwamyGreedyApproximator, OptimalSolver, NisanGreedyDemandApproximator

__author__ = 'Usiel'


class Auction:
    def __init__(self, supply, agents, log=ConsoleLogger()):
        """
        :param supply: Number of copies of identical item.
        :param agents: List of agents to participate. Need to implement query_demand(.) and query_value(.).
        """
        self.supply = supply
        self.agents = agents
        self.solver = BendersSolver(self.supply,
                                    self.agents,
                                    LaviSwamyGreedyApproximator(self.supply, self.agents, log),
                                    log)
        self.expected_price = dict()
        self.log = log

    def start_auction(self):
        allocations = self.solver.solve()
        optimal_with_agent = self.calculate_social_welfare(allocations)

        for agent in self.agents:
            other_agents = [a for a in self.agents if a != agent]
            solver = BendersSolver(self.supply, other_agents,
                                   LaviSwamyGreedyApproximator(
                                       self.supply,
                                       other_agents,
                                       BlackHoleLogger()),
                                   BlackHoleLogger())
            allocations_without_agent = solver.solve()

            optimal_without_agent = -solver.z.x  # = self.calculate_social_welfare(allocations_without_agent)
            other_agents_valuations = sum([allocation.get_expected_social_welfare_without_agent(agent.id)
                                           for allocation in allocations.itervalues()])

            vcg_payoff = optimal_with_agent - optimal_without_agent
            vcg_price = optimal_without_agent - other_agents_valuations

            self.expected_price[agent.id] = vcg_price

            print 'Marginal Economy - Sum V-1 = %s - %s = %s' % (
            optimal_without_agent, other_agents_valuations, self.expected_price[agent.id])

        for price in self.expected_price.iteritems():
            self.log.log('Agent %s has expected VCG price %s' % (price[0], price[1]))

    def calculate_social_welfare(self, allocations):
        return sum([allocation.expected_social_welfare for allocation in allocations.itervalues()])


class AscendingAuction:
    def __init__(self, supply, agents, log=ConsoleLogger()):
        """
        :param supply: Number of copies of identical item.
        :param agents: List of agents to participate. Need to implement query_demand(.) and query_value(.).
        """
        self.supply = supply
        self.agents = agents
        self.expected_price = {key.id: None for key in self.agents}
        self.marginal_economies = {key.id: None for key in self.agents}
        self.log = log
        self.marginal_economies = {key.id: None for key in self.agents}
        self.step_size = 0.05

    def start_auction(self):
        p = 0.
        total_demand = None
        while total_demand is None or total_demand >= self.supply:
            p += self.step_size
            total_demand = 0
            demands, total_demand, min_coeff = self.get_demands_at_price(p, self.agents)

            # now check if without agent i, is there still overdemand?
            # for agent in self.agents:
            #     # check if we already know vcg price
            #     if self.marginal_economies[agent.id] is None:
            #         marginal_agents = [copy.copy(a) for a in self.agents if agent != a]
            #         marginal_demands, total_marginal_demands, marginal_min_coeff = self.get_demands_at_price(p - self.step_size,
            #                                                                              marginal_agents)
            #         if total_marginal_demands <= self.supply:
            #             print 'p=%s agent %s out' % (p - self.step_size, agent.id)
            #             marginal_agents = self.get_agents_with_relevant_valuations(marginal_agents, marginal_demands)
            #             marginal_solver = BendersSolver(self.supply,
            #                                             marginal_agents,
            #                                             LaviSwamyGreedyApproximator(self.supply, marginal_agents,
            #                                                                         BlackHoleLogger()),
            #                                             BlackHoleLogger())
            #             marginal_solver.solve()
            #             self.marginal_economies[agent.id] = -marginal_solver.objective

        non_marginal_bidders = [agent for agent in self.agents if agent.id in [demand[0] for demand in demands.iteritems() if demand[1]]]
        marginal_bidders = [agent for agent in self.agents if agent not in non_marginal_bidders]
        p -= self.step_size
        non_marginal_demands, non_marginal_total_demand, non_marginal_min_coeff = self.get_demands_at_price(p, non_marginal_bidders)
        marginal_demands, marginal_total_demand, marginal_min_coeff = self.get_demands_at_price(p, marginal_bidders)

        marginal_coeff = (self.supply - non_marginal_total_demand) / marginal_total_demand if marginal_total_demand > 0 else 0
        marginal_total_demand = marginal_coeff * marginal_total_demand
        for agent_id in marginal_demands:
            marginal_demands[agent_id] = {Valuation(demand.quantity * marginal_coeff, demand.valuation * marginal_coeff) for demand in marginal_demands[agent_id]}
        print marginal_coeff
        z = marginal_demands.copy()
        z.update(non_marginal_demands)
        demands = z
        total_demand = marginal_total_demand + non_marginal_total_demand

        return self.calculate_fractional_assignments(demands, total_demand, min_coeff, self.agents)
        print p

        # for agent_demand in demands.iteritems():
        #     for demand in agent_demand[1]:
        #         print 'p=%s , D_%s(%s)=%s' % (p, agent_demand[0], p, demand.quantity)
        # print 'D(%s)=%s' % (p, total_demand)
        #
        # agents_with_relevant_valuations = self.get_agents_with_relevant_valuations(self.agents, demands)
        #
        # solver = BendersSolver(self.supply,
        #                        agents_with_relevant_valuations,
        #                        LaviSwamyGreedyApproximator(self.supply, agents_with_relevant_valuations, self.log),
        #                        self.log)
        # allocations = solver.solve()
        #
        # for agent in self.agents:
        #     other_agents_valuations = sum([allocation.get_expected_social_welfare_without_agent(agent.id)
        #                                    for allocation in allocations.itervalues()])
        #     # if marginal economy exists, otherwise use full economy (can happen, if agent i does not drop out
        #     marginal_economy = self.marginal_economies[agent.id] if self.marginal_economies[agent.id] else -solver.objective
        #     self.expected_price[agent.id] = marginal_economy  - other_agents_valuations
        #
        # for price in self.expected_price.iteritems():
        #     self.log.log('Agent %s has expected VCG price %s' % (price[0], price[1]))
        #
        # OptimalSolver(supp, agents_with_relevant_valuations, 2, False)

    def get_demands_at_price(self, price, agents):
        total_demand = 0
        demands = {key.id: [] for key in agents}
        min_demands = {key.id: 0. for key in agents}
        max_demands = {key.id: 0. for key in agents}
        for agent in agents:
            demand_set = agent.query_demand_set(price, supp)
            demands[agent.id] = demand_set
            if demands[agent.id]:
                min_demands[agent.id] = min(demand.quantity for demand in demands[agent.id])
                max_demands[agent.id] = max(demand.quantity for demand in demands[agent.id])
        sum_max_demands = sum(max_demands.itervalues())
        sum_diff = sum(min_demands[agent.id] - max_demands[agent.id] for agent in agents)
        min_coeff = (self.supply - sum_max_demands) / sum_diff if sum_diff != 0 else 1
        if min_coeff < 1.:
            total_demand = sum(min_demands[agent.id] * min_coeff + max_demands[agent.id] * (1 - min_coeff) for agent in agents)
        else:
            total_demand = sum(min_demands.itervalues())

        #self.calculate_fractional_assignments(demands, total_demand, min_coeff, agents)
        return demands, total_demand, min_coeff

    def get_agents_with_relevant_valuations(self, agents, demands):
        agents_copy = copy.deepcopy(agents)
        for agent in agents_copy:
            for val in agent.valuations:
                if not any(demand.quantity == val.quantity for demand in demands[agent.id]):
                    val.valuation = 0
        return agents_copy

    def calculate_fractional_assignments(self, demands, total_demand, min_coeff, agents):
        sw = 0.
        for agent in agents:
            try:
                if demands[agent.id]:
                    min_demand = min(demands[agent.id], key = lambda d: d.quantity)
                    max_demand = max(demands[agent.id], key = lambda d: d.quantity)
                    print 'Agent %s gets %s items: %s' % (agent.id, min_demand.quantity, min_coeff)
                    print 'Agent %s gets %s items: %s' % (agent.id, max_demand.quantity, (1.-min_coeff))
                    valuation = min_demand.valuation * min_coeff + max_demand.valuation * (1.-min_coeff)
                    print 'Valuation for this agent: %s' % valuation
                    sw += valuation
            except KeyError:
                pass
        print sw
        return sw

class PrimalDualAuction:
    def __init__(self, supply, agents, log=ConsoleLogger()):
        """
        :param supply: Number of copies of identical item.
        :param agents: List of agents to participate. Need to implement query_demand(.) and query_value(.).
        """
        self.supply = supply
        self.agents = agents
        self.expected_price = {key.id: None for key in self.agents}
        self.marginal_economies = {key.id: None for key in self.agents}
        self.log = log
        self.marginal_economies = {key.id: None for key in self.agents}
        self.step_size = 0.1
        self.obj = 0.

    def start_auction(self):
        p = 0.
        total_demand = None
        status = GRB.INFEASIBLE
        while status == GRB.INFEASIBLE: #total_demand is None or total_demand >= self.supply:
            p += self.step_size
            total_demand = 0
            demands = self.get_demands_at_price(p, self.agents)
            demands_next = self.get_demands_at_price(p + epsilon, self.agents)
            m = self.solve_restricted_primal(demands, demands_next, p)

            status = m.status
            print p
        return m.getObjective().getValue()

    def solve_restricted_primal(self, demands, demands_next, p):
        self.obj = 0.
        m = Model("multi-unit-auction")
        # self.m.params.LogToConsole = 0
        self.allocation_vars = dict()
        for agent in self.agents:
            for i in range(1, self.supply + 1):
                self.allocation_vars[agent.id, i] = m.addVar(lb=0., ub=1., vtype=GRB.CONTINUOUS,
                                                                  name='x_%s_%s' % (agent.id, i))
        m.update()
        for agent in self.agents:
            if len(demands[agent.id]) > 0 and len(demands_next[agent.id]) > 0:
                m.addConstr(quicksum(self.allocation_vars[agent.id, i] for i in range(1, self.supply + 1)),
                                 GRB.EQUAL, 1, name="u_%s_strict" % agent.id)
            else:
                m.addConstr(quicksum(self.allocation_vars[agent.id, i] for i in range(1, self.supply + 1)),
                                 GRB.LESS_EQUAL, 1, name="u_%s" % agent.id)
            for j in range(1, self.supply + 1):
                if j not in [demand.quantity for demand in demands[agent.id]]:
                    m.addConstr(self.allocation_vars[agent.id, j], GRB.EQUAL, 0, name='x_%s_%s_undemanded' % (agent.id, j))

        if p > 0:
            m.addConstr(
                quicksum(self.allocation_vars[agent.id, i] * i for i in range(1, self.supply + 1) for agent in self.agents),
                GRB.EQUAL, self.supply, name="price_strict")
        else:
            m.addConstr(
                quicksum(self.allocation_vars[agent.id, i] * i for i in range(1, self.supply + 1) for agent in self.agents),
                GRB.LESS_EQUAL, self.supply, name="price")
        obj_expr = LinExpr()
        for agent in self.agents:
            for valuation in agent.valuations:
                obj_expr.addTerms(valuation.quantity, self.allocation_vars[agent.id, valuation.quantity])
        m.setObjective(obj_expr, GRB.MAXIMIZE)
        m.update()
        m.optimize()

        m.write('optimal-lp.lp')

        if m.status == GRB.OPTIMAL:
            m.write('optimal-lp.sol')
            for v in [v for v in m.getVars() if v.x != 0.]:
                print('%s %g' % (v.varName, v.x))

            print ''
            print 'CONSTRAINTS:'

            for l in m.getConstrs():
                if l.Pi > 0:
                    print('%s %g' % (l.constrName, l.Pi))

            print m.getObjective().getValue()

        return m

    def get_demands_at_price(self, price, agents):
        demands = {key.id: [] for key in agents}
        for agent in agents:
            demand_set = agent.query_demand_set(price, supp)
            demands[agent.id] = demand_set
        return demands


# example used in paper
agent1 = ManualAgent([Valuation(1, 10.), Valuation(2, 10.), Valuation(3, 10.), Valuation(4, 10.)], 1)
agent2 = ManualAgent([Valuation(1, 10.), Valuation(2, 10.), Valuation(3, 10.), Valuation(4, 12.)], 2)
agent3 = ManualAgent([Valuation(1, 10.), Valuation(2, 13.), Valuation(3, 14.), Valuation(4, 15.)], 3)
auction_agents_m = [agent1, agent2, agent3]

# automatically generated
auction_supply = 9
auction_agents = generate_randomized_agents(auction_supply, 5)
a = Auction(auction_supply, auction_agents)

a1 = ManualAgent([Valuation(1, 6.), Valuation(2, 6.), Valuation(3, 6.), Valuation(4, 9.)], 0)
a2 = ManualAgent([Valuation(1, 1.), Valuation(2, 4.), Valuation(3, 4.), Valuation(4, 6.)], 1)
agents_non_ascending = [a1]#, a2]

agent1 = ManualAgent([Valuation(1, 6.), Valuation(2, 6.), Valuation(3, 6.), Valuation(4, 6.)], 0)
agent2 = ManualAgent([Valuation(1, 1.), Valuation(2, 4.), Valuation(3, 4.), Valuation(4, 6.)], 1)
#agent20 = ManualAgent([Valuation(1, 0.), Valuation(2, 2.), Valuation(3, 2.), Valuation(4, 2.)], 20)
#agent200 = ManualAgent([Valuation(1, 1.), Valuation(2, ), Valuation(3, 4.5), Valuation(4, 4.5)], 200)
#agent2000 = ManualAgent([Valuation(1, 0.), Valuation(2, 3.5), Valuation(3, 4.5), Valuation(4, 4.5)], 2000)
agent3 = ManualAgent([Valuation(1, 0.), Valuation(2, 1.), Valuation(3, 1.), Valuation(4, 1.)], 2)
auction_agents_m = [agent1, agent2, agent3]

ausubel0 = ManualAgent(
    [Valuation(1, 123.), Valuation(2, 236.), Valuation(3, 339.), Valuation(4, 339.), Valuation(5, 339.)], 0)
ausubel1 = ManualAgent([Valuation(1, 75.), Valuation(2, 80.), Valuation(3, 83.), Valuation(4, 83.), Valuation(5, 83.)],
                       1)
ausubel2 = ManualAgent(
    [Valuation(1, 125.), Valuation(2, 250.), Valuation(3, 299.), Valuation(4, 299.), Valuation(5, 299.)], 2)
ausubel3 = ManualAgent(
    [Valuation(1, 85.), Valuation(2, 150.), Valuation(3, 157.), Valuation(4, 157.), Valuation(5, 157.)], 3)
ausubel4 = ManualAgent([Valuation(1, 45.), Valuation(2, 70.), Valuation(3, 75.), Valuation(4, 75.), Valuation(5, 75.)],
                       4)

ausubel_agents = [ausubel0, ausubel1, ausubel2, ausubel3, ausubel4]

w1 = ManualAgent([Valuation(1, 0.), Valuation(2, 0.), Valuation(3, 3.)], 0)
w2 = ManualAgent([Valuation(1, 2.), Valuation(2, 2.), Valuation(3, 2.)], 1)
w_agents = [w1, w2]

e1 = ManualAgent([Valuation(1, 0.), Valuation(2, 2.)], 0)
e2 = ManualAgent([Valuation(1, 1.), Valuation(2, 1.)], 1)
equi_agents = [e1, e2]

a = agents_non_ascending
supp = len(a[0].valuations)

auction2 = Auction(supp, copy.deepcopy(a))
auction = AscendingAuction(supp, a)
pdauction = PrimalDualAuction(supp, a)

sw = pdauction.start_auction()

print''
print '############### ASCENDING AUCTION'
print''
#sw = auction.start_auction()

print''
print '############### DW DECO AUCTION'
print ''
#auction2.start_auction()
#
# for agent in ag:
# print agent.id
# pprint.pprint(agent.queried)
solver = OptimalSolver(supp, a, 2)
opt_sw = solver.m.getObjective().getValue()
if opt_sw != sw:
    print 'OPT: %s | ASC_SW: %s' % (opt_sw, sw)
