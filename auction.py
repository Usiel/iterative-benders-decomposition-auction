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

            optimal_without_agent = -solver.z.x # = self.calculate_social_welfare(allocations_without_agent)
            other_agents_valuations = sum([allocation.get_expected_social_welfare_without_agent(agent.id)
                                           for allocation in allocations.itervalues()])

            vcg_payoff = optimal_with_agent - optimal_without_agent
            vcg_price = optimal_without_agent - other_agents_valuations

            self.expected_price[agent.id] = vcg_price

            print 'Marginal Economy - Sum V-1 = %s - %s = %s' % (optimal_without_agent, other_agents_valuations, self.expected_price[agent.id])

        for price in self.expected_price.iteritems():
            self.log.log('Agent %s has expected VCG price %s' % (price[0], price[1]))

    def calculate_social_welfare(self, allocations):
        return sum([allocation.expected_social_welfare for allocation in allocations.itervalues()])


# example used in paper
agent1 = ManualAgent([Valuation(1, 10.), Valuation(2, 10.), Valuation(3, 10.), Valuation(4, 10.)], 1)
agent2 = ManualAgent([Valuation(1, 10.), Valuation(2, 10.), Valuation(3, 10.), Valuation(4, 12.)], 2)
agent3 = ManualAgent([Valuation(1, 10.), Valuation(2, 13.), Valuation(3, 14.), Valuation(4, 15.)], 3)
auction_agents_m = [agent1, agent2, agent3]

# automatically generated
auction_supply = 9
auction_agents = generate_randomized_agents(auction_supply, 2)
a = Auction(auction_supply, auction_agents)

a1 = ManualAgent([Valuation(1, 6.), Valuation(2, 6.), Valuation(3, 6.), Valuation(4, 9.)], 0)
a2 = ManualAgent([Valuation(1, 1.), Valuation(2, 4.), Valuation(3, 4.), Valuation(4, 6.)], 1)
agents = [a1, a2]

agent1 = ManualAgent([Valuation(1, 6.), Valuation(2, 6.), Valuation(3, 6.), Valuation(4, 6.)], 0)
agent2 = ManualAgent([Valuation(1, 1.), Valuation(2, 4.), Valuation(3, 4.), Valuation(4, 6.)], 1)
agent3 = ManualAgent([Valuation(1, 0.), Valuation(2, 1.), Valuation(3, 1.), Valuation(4, 1.)], 2)
auction_agents_m = [agent1, agent2, agent3]

ausubel0 = ManualAgent([Valuation(1, 123.), Valuation(2, 236.), Valuation(3, 339.), Valuation(4, 339.), Valuation(5, 339.)], 0)
ausubel1 = ManualAgent([Valuation(1, 75.), Valuation(2, 80.), Valuation(3, 83.), Valuation(4, 83.), Valuation(5, 83.)], 1)
ausubel2 = ManualAgent([Valuation(1, 125.), Valuation(2, 250.), Valuation(3, 299.), Valuation(4, 299.), Valuation(5, 299.)], 2)
ausubel3 = ManualAgent([Valuation(1, 85.), Valuation(2, 150.), Valuation(3, 157.), Valuation(4, 157.), Valuation(5, 157.)], 3)
ausubel4 = ManualAgent([Valuation(1, 45.), Valuation(2, 70.), Valuation(3, 75.), Valuation(4, 75.), Valuation(5, 75.)], 4)

ausubel_agents = [ausubel0, ausubel1, ausubel2, ausubel3, ausubel4]

e1 = ManualAgent([Valuation(1, 0.), Valuation(2, 2.)], 0)
e2 = ManualAgent([Valuation(1, 1.), Valuation(2, 1.)], 1)
equi_agents = [e1, e2]

a = auction_agents
supp = len(a[0].valuations)

OptimalSolver(supp, a, 2)

total_demand = supp + 1
p = 0.
while total_demand > supp:
    p += 0.1
    total_demand = 0
    demands = {key.id: [] for key in a}
    for agent in a:
        demand_set = agent.query_demand_set(p, supp)
        demands[agent.id] = demand_set
        for demand in demand_set:
            total_demand += demand.quantity

p -= 0.1
total_demand = 0
demands = {key.id: [] for key in a}
for agent in a:
    demand_set = agent.query_demand_set(p, supp)
    demands[agent.id] = demand_set
    #pprint.pprint(demand_set)
    for demand in demand_set:
        total_demand += demand.quantity

for agent_demand in demands.iteritems():
    for demand in agent_demand[1]:
        print 'p=%s , D_%s(%s)=%s' % (p, agent_demand[0], p, demand.quantity)
print 'D(%s)=%s' % (p, total_demand)


for agent in a:
    for val in agent.valuations:
        if not any(demand.quantity == val.quantity for demand in demands[agent.id]):
            val.valuation = 0

auction = Auction(supp, a)

auction.start_auction()

#for agent in ag:
    #print agent.id
    #pprint.pprint(agent.queried)
