import copy
import math
import pprint
import itertools
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
            demands, total_demand = self.get_demands_at_price(p, self.agents)

            # now check if without agent i, is there still overdemand?
            for agent in self.agents:
                # check if we already know vcg price
                if self.marginal_economies[agent.id] is None:
                    marginal_agents = [copy.copy(a) for a in self.agents if agent != a]
                    marginal_demands, total_marginal_demands = self.get_demands_at_price(p - self.step_size,
                                                                                         marginal_agents)
                    if total_marginal_demands <= self.supply:
                        print 'p=%s agent %s out' % (p - self.step_size, agent.id)
                        marginal_agents = self.get_agents_with_relevant_valuations(marginal_agents, marginal_demands)
                        marginal_solver = BendersSolver(self.supply,
                                                        marginal_agents,
                                                        LaviSwamyGreedyApproximator(self.supply, marginal_agents,
                                                                                    BlackHoleLogger()),
                                                        BlackHoleLogger())
                        marginal_solver.solve()
                        self.marginal_economies[agent.id] = -marginal_solver.objective

        p -= self.step_size
        demands, total_demand = self.get_demands_at_price(p, self.agents)

        for agent_demand in demands.iteritems():
            for demand in agent_demand[1]:
                print 'p=%s , D_%s(%s)=%s' % (p, agent_demand[0], p, demand.quantity)
        print 'D(%s)=%s' % (p, total_demand)

        agents_with_relevant_valuations = self.get_agents_with_relevant_valuations(self.agents, demands)

        solver = BendersSolver(self.supply,
                               agents_with_relevant_valuations,
                               LaviSwamyGreedyApproximator(self.supply, agents_with_relevant_valuations, self.log),
                               self.log)
        allocations = solver.solve()

        for agent in self.agents:
            other_agents_valuations = sum([allocation.get_expected_social_welfare_without_agent(agent.id)
                                           for allocation in allocations.itervalues()])
            # if marginal economy exists, otherwise use full economy (can happen, if agent i does not drop out
            marginal_economy = self.marginal_economies[agent.id] if self.marginal_economies[agent.id] else -solver.objective
            self.expected_price[agent.id] = marginal_economy  - other_agents_valuations

        for price in self.expected_price.iteritems():
            self.log.log('Agent %s has expected VCG price %s' % (price[0], price[1]))

    def get_demands_at_price(self, price, agents):
        total_demand = 0
        demands = {key.id: [] for key in agents}
        for agent in agents:
            demand_set = agent.query_demand_set(price, supp)
            demands[agent.id] = demand_set
            for demand in demand_set:
                total_demand += demand.quantity / len(demand_set)
        return demands, total_demand

    def get_agents_with_relevant_valuations(self, agents, demands):
        agents_copy = copy.deepcopy(agents)
        for agent in agents_copy:
            for val in agent.valuations:
                if not any(demand.quantity == val.quantity for demand in demands[agent.id]):
                    val.valuation = 0
        return agents_copy


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
agents_non_ascending = [a1, a2]

agent1 = ManualAgent([Valuation(1, 6.), Valuation(2, 6.), Valuation(3, 6.), Valuation(4, 10.)], 0)
agent2 = ManualAgent([Valuation(1, 1.), Valuation(2, 4.), Valuation(3, 4.), Valuation(4, 15.)], 1)
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

a = auction_agents
supp = len(a[0].valuations)

OptimalSolver(supp, a, 2)

auction2 = Auction(supp, copy.deepcopy(a))
auction = AscendingAuction(supp, a)

print''
print '############### ASCENDING AUCTION'
print''
auction.start_auction()

print''
print '############### DW DECO AUCTION'
print ''
auction2.start_auction()
#
# for agent in ag:
# print agent.id
# pprint.pprint(agent.queried)
