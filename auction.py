import math

from agent import generate_randomized_agents, ManualAgent
from common import epsilon, Valuation, ConsoleLogger, BlackHoleLogger
from solver import BendersSolver, LaviSwamyGreedyApproximator, OptimalSolver

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

        for price in self.expected_price.iteritems():
            self.log.log('Agent %s has expected VCG price %s' % (price[0], price[1]))

    def calculate_social_welfare(self, allocations):
        return sum([allocation.expected_social_welfare for allocation in allocations.itervalues()])


# example used in paper
agent1 = ManualAgent([Valuation(1, 6.), Valuation(2, 6.), Valuation(3, 6.), Valuation(4, 9.)], 1)
agent2 = ManualAgent([Valuation(1, 1.), Valuation(2, 4.), Valuation(3, 4.), Valuation(4, 6.)], 2)
#agent3 = ManualAgent([Valuation(1, 1.), Valuation(2, 4.), Valuation(3, 4.), Valuation(4, 4.)], 3)
auction_agents_m = [agent1, agent2]#, agent3]

# automatically generated
auction_supply = 14
auction_agents = generate_randomized_agents(auction_supply, 50)
# a = Auction(auction_supply, auction_agents)

a = Auction(4, auction_agents_m)

a.start_auction()
