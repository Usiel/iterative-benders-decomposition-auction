import pprint
from agent import ManualAgent
from common import Valuation, ConsoleLogger, Allocation
from solver import LaviSwamyGreedyApproximator, OptimalSolver, NisanGreedyDemandApproximator

__author__ = 'Usiel'


class DwSolver:
    def __init__(self, agents, supply):
        self.agents = agents
        self.supply = supply

        self.approximator = LaviSwamyGreedyApproximator(supply, agents, ConsoleLogger())

        m_range = range(0, len(self.agents) + 2)
        self.base = []
        for i in m_range:
            row = []
            for j in m_range:
                if i == j:
                    row += [1.]
                else:
                    row += [0.]
            self.base.append(row)
        self.z = [0. for i in m_range] + [0.]
        self.b = [1 / self.approximator.gap for i in range(0, len(self.agents))] + [supply / self.approximator.gap] + [1.]
        self.row_names = ['s%s' % i for i, row in enumerate(self.base) if i < len(self.base)-1] + ['l0']
        self.cost = 0.
        self.allocations = dict()
        self.allocations[0] = Allocation()

    @property
    def utilities(self):
        return self.z_to_utilities(self.z)

    @property
    def price(self):
        return self.z_to_price(self.z)

    def z_to_price(self, z):
        return -z[len(self.agents)]

    def z_to_utilities(self, z):
        return dict(enumerate(z[0:len(self.agents)]))

    def iterate(self):
        print ''
        allocation = self.approximator.approximate(self.price, {k: -u for k,u in self.utilities.iteritems()})

        new_base = self.base[:]
        new_b = self.b[:]
        new_z = self.z[:]

        # A*X_j
        constraints = [1. if any([assignment.agent_id == i for assignment in allocation.assignments]) else 0. for i in
                       range(0, len(self.agents))] + [allocation.quantity_assigned] + [1.]

        # entering column
        y_k = []
        for row in new_base:
            y_k += [sum([base_value * constraint_value for base_value, constraint_value in zip(row, constraints)])]

        self.print_tableau(y_k)

        # leaving variable row index
        # print 'Recommendation is row %s' % self.get_leaving_row_index(new_b, y_k)
        #r = None
        #while r == None:
        #     input = int(raw_input('row index please: '))
        #     if True or y_k[input] > 0:
        #        r = input

        r = self.get_leaving_row_index(new_b, y_k, new_base)

        # divide selected row by y_kr
        new_base = [base_row if index != r else [
            base_value / y_k[r] for base_value in base_row] for index, base_row in
                    enumerate(new_base)]
        new_b = [b_value if index != r else b_value / y_k[r] for index, b_value in enumerate(new_b)]

        # add -y_kr * pivot_row to each row (except pivot row)
        new_base = [base_row if index == r else
                    [base_cell + (new_cell * -y_k[index]) for base_cell, new_cell in
                     zip(base_row, new_base[r])] for index, base_row in
                    enumerate(new_base)]
        new_b = [b_value if index == r else b_value + (new_b[r] * -y_k[index]) for
                 index, b_value in enumerate(new_b)]

        # add (z-c) * new_row + row_z
        # z - c = sum(valuations) - quantity * price - utility * x_ij
        social_welfare = sum([assignment.valuation for assignment in allocation.assignments]) \
                         - allocation.quantity_assigned * self.price \
                         + sum([self.utilities[agent.id]
                                if any([assignment.agent_id == agent.id for assignment in allocation.assignments])
                                else 0
                                for agent in self.agents])
        #social_welfare = 1 if new_z[len(new_z)-2] == 0. else 0

        new_z = [z_value - (social_welfare * pivot_row_value) for z_value, pivot_row_value in zip(new_z, new_base[r] + [new_b[r]])]

        print 'z - c = %s' % social_welfare

        predicted_allocation = None #self.approximator.approximate(self.z_to_price(new_z), {k: -u for k,u in self.z_to_utilities(new_z).iteritems()})
        price_row_selected = r == len(self.agents)
        if False and not price_row_selected and (len(predicted_allocation.assignments) == 0 or any(b < 0 for b in new_b)) and raw_input('danger... OK y?') != 'y':
            print 'We need to increase the price I think or we are finished!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
        else:
            self.allocations[len(self.allocations)] = allocation
            self.row_names[r] = 'l%s' % (len(self.allocations)-1)
            self.base = new_base
            self.b = new_b
            self.z = new_z

        self.print_tableau()

        return True

    def get_leaving_row_index(self, b, y_k, base):
        # return int(raw_input('leaving var row index: '))
        ratios = {index: b_value/y_value for index, (b_value, y_value) in enumerate(zip(b, y_k)) if y_value > 0}
        row_index = min(ratios.iteritems(), key=lambda r: r[1])[0]
        print ''
        print 'Pivoting at row %s' % row_index
        print ''
        return row_index

    def print_tableau(self, y_k = None):
        print 'z \t | \t',
        for i, z in enumerate(self.z):
            if i == len(self.z)-2:
                print '%s \t | \t' % z,
            else:
                print '%s \t' % z,
        print ''
        print '-----------------------------------------------------------'

        for index, row in enumerate(self.base):
            print '%s \t | \t' % self.row_names[index],
            for b in row:
                print '%s \t' % b,
            print '| \t %s' % self.b[index],
            if y_k:
                print '\t | \t %s' % y_k[index]
            else:
                print ''


a1 = ManualAgent([Valuation(1, 6.), Valuation(2, 6.), Valuation(3, 6.), Valuation(4, 9.)], 0)
a2 = ManualAgent([Valuation(1, 1.), Valuation(2, 4.), Valuation(3, 4.), Valuation(4, 6.)], 1)
agents = [a1, a2]

agent1 = ManualAgent([Valuation(1, 0.5), Valuation(2, 0.), Valuation(3, 0.), Valuation(4, 0.)], 0)
agent2 = ManualAgent([Valuation(1, 0.), Valuation(2, 0.25), Valuation(3, 0.), Valuation(4, 0.25)], 1)
agent3 = ManualAgent([Valuation(1, 0.), Valuation(2, 0.), Valuation(3, 0.), Valuation(4, 0.)], 2)
auction_agents_m = [agent1, agent2, agent3]

ausubel0 = ManualAgent([Valuation(1, 123.), Valuation(2, 236), Valuation(3, 339), Valuation(4, 339), Valuation(5, 339)], 0)
ausubel1 = ManualAgent([Valuation(1, 75.), Valuation(2, 80), Valuation(3, 83), Valuation(4, 83), Valuation(5, 83)], 1)
ausubel2 = ManualAgent([Valuation(1, 125.), Valuation(2, 250), Valuation(3, 299), Valuation(4, 299), Valuation(5, 299)], 2)
ausubel3 = ManualAgent([Valuation(1, 85.), Valuation(2, 150), Valuation(3, 157), Valuation(4, 157), Valuation(5, 157)], 3)
ausubel4 = ManualAgent([Valuation(1, 45.), Valuation(2, 70), Valuation(3, 75), Valuation(4, 75), Valuation(5, 75)], 4)

ausubel_agents = [ausubel0, ausubel1, ausubel2, ausubel3, ausubel4]

e1 = ManualAgent([Valuation(1, 0.), Valuation(2, 4./3.)], 0)
e2 = ManualAgent([Valuation(1, 4./3.), Valuation(2, 0)], 1)
equi_agents = [e1, e2]

a = ausubel_agents
supp = len(a[0].valuations)

s = DwSolver(a, supp)
while raw_input("press enter to continue, q to break ") != "q":
    s.iterate()
for item in s.allocations.iteritems():
    if item[1].probability > 0 or True:
        # noinspection PyArgumentList
        print('%s (%s)' % (item[0], item[1].probability))
        item[1].print_me(ConsoleLogger())
        print ''

OptimalSolver(supp, a, 1)