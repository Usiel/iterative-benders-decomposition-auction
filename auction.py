import math

from agent import generate_randomized_agents, ManualAgent
from common import epsilon, Valuation
from solver import BendersSolver, LaviSwamyGreedyApproximator, OptimalSolver

__author__ = 'Usiel'


class Auction:
    def __init__(self, supply, agents):
        """
        :param supply: Number of copies of identical item.
        :param agents: List of agents to participate. Need to implement query_demand(.) and query_value(.).
        """
        self.supply = supply
        self.agents = agents
        self.approximator = LaviSwamyGreedyApproximator(self.supply, self.agents)
        self.b = [(1. / self.approximator.gap) for i in range(0, len(self.agents))]
        self.b.append(self.supply / self.approximator.gap)
        self.solver = BendersSolver(self.b, self.agents)
        self.allocations = {'X0': []}

    def iterate(self):
        """
        Performs one iteration of the Bender Auction. Optimizes current master problem, requests an approximate \
        allocation based on current prices and utilities, calculates phi with current optimal values of master problem \
        and then compares this with current z value.
        :return: False if auction is done and True if a Bender's cut has been added and the auction continues.
        """
        iteration = len(self.allocations)

        print ''
        print '######## ITERATION %s ########' % iteration

        self.solver.optimize()
        # allocation := X
        allocation = self.approximator.approximate(self.solver.price, self.solver.utilities)

        # first_term - second_term = w*b - (c + wA) * X
        # first_term is w*b
        first_term = sum([-w * b for w, b in zip(self.solver.utilities.values() + [self.solver.price], self.b)])
        # second_term is (c + wA) * X
        second_term = 0
        for assignment in allocation:
            # for each x_ij which is 1 we generate c + wA which is (for MUA): v_i(j) + price * j + u_i
            second_term += self.solver.price * assignment.quantity
            second_term += -self.solver.utilities[assignment.agent_id]
            second_term += assignment.valuation
        phi = first_term - second_term
        print 'phi = %s - %s = %s' % (first_term, second_term, phi)

        # check if phi with current result of master-problem is z (with tolerance)
        if math.fabs(phi - self.solver.z.x) < epsilon:
            self.print_results()

            # for checking we solve the program in round
            OptimalSolver(self.supply, self.agents, self.approximator.gap)
            return False
        # otherwise continue and add cut based on this iteration's allocation
        else:
            allocation_name = 'X%s' % iteration
            self.allocations[allocation_name] = allocation
            self.solver.add_benders_cut(allocation, allocation_name)
            return True

    def print_results(self):
        """
        Prints results in console.
        """
        print ''
        print '####### SUMMARY #######'
        print ''
        for item in self.allocations.iteritems():
            # noinspection PyArgumentList
            print '%s (%s)' % (item[0], self.solver.m.getConstrByName(item[0]).pi)
            for assignment in item[1]:
                assignment.print_me()
            print ''

        for agent in self.agents:
            vcg_price = sum(self.solver.m.getConstrByName(alloc[0]).pi *
                            sum([assignment.vcg_price for assignment in alloc[1] if assignment.agent_id == agent.id])
                            for alloc in self.allocations.iteritems())
            if vcg_price > 0:
                print 'Agent %s E[payment]=%s' % (agent.id, vcg_price)

        if self.solver.price_changed:
            print 'Price has decreased at some point.'
        print '%s iterations needed' % len(self.allocations)
        print 'E[Social welfare] is %s' % -self.solver.z.x


# example used in paper
agent1 = ManualAgent([Valuation(1, 6.), Valuation(2, 6.), Valuation(3, 6.), Valuation(4, 6.)], 1)
agent2 = ManualAgent([Valuation(1, 1.), Valuation(2, 4.), Valuation(3, 4.), Valuation(4, 6.)], 2)
agent3 = ManualAgent([Valuation(1, 0.), Valuation(2, 1.), Valuation(3, 1.), Valuation(4, 1.)], 3)
auction_agents_m = [agent1, agent2, agent3]

# automatically generated
auction_supply = 40
auction_agents = generate_randomized_agents(auction_supply, 90)
#a = Auction(auction_supply, auction_agents)

a = Auction(4, auction_agents_m)

flag = True
while flag:
    flag = a.iterate()
