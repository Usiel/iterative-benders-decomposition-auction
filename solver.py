import math
import pprint

from gurobipy.gurobipy import Model, GRB, LinExpr, GurobiError, quicksum

from common import Assignment, epsilon, Allocation

__author__ = 'Usiel'
iteration_abort_threshold = 100

class BendersSolver:
    def __init__(self, supply, agents, approximator, log):
        """
        :param b: b of LP. If n=len(agents) then the first n values are 1./alpha and n+1 value is supply/alpha.
        :param agents: List of agents.
        """
        # Setting up master problem
        self.m = Model("master-problem")
        self.m.params.LogToConsole = 0
        # noinspection PyArgumentList,PyArgumentList,PyArgumentList
        self.z = self.m.addVar(lb=-GRB.INFINITY, ub=GRB.INFINITY, name="z")
        self.approximator = approximator
        self.agents = agents
        self.log = log

        self.allocations = {'X0': Allocation()}

        self.b = [(1. / self.approximator.gap) for i in range(0, len(self.agents))]
        self.b.append(supply / self.approximator.gap)

        # noinspection PyArgumentList,PyArgumentList,PyArgumentList
        self.price_var = self.m.addVar(lb=-GRB.INFINITY, ub=0, name="price")
        self.utility_vars = dict()
        for agent in self.agents:
            # noinspection PyArgumentList,PyArgumentList,PyArgumentList
            self.utility_vars[agent.id] = self.m.addVar(lb=-GRB.INFINITY, ub=0, name="u_%s" % agent.id)

        self.m.update()

        # Initial constraints for empty allocation
        self.add_benders_cut(Allocation(), "X0")
        self.old_price_constraint = 0.
        self.add_price_constraint(0.)
        self.m.setObjective(self.z, GRB.MAXIMIZE)

        self.price_changed = False
        self.give_second_chance = True
        self.old_z = 0.
        self.old_utilities = dict()

    @property
    def price(self):
        """
        :return: Returns current price (positive).
        """
        try:
            return math.fabs(self.price_var.x)
        except GurobiError:
            return None

    @property
    def utilities(self):
        """
        :return: Returns current utilities (positive): dict(agent_id: utility)
        """
        return dict((v[0], math.fabs(v[1].x)) for v in self.utility_vars.iteritems())

    @property
    def objective(self):
        try:
            return self.z.x
        except GurobiError:
            return 0.

    def solve(self):
        while self.iterate():
            pass
        return self.allocations

    def iterate(self):
        """
        Performs one iteration of the Bender Auction. Optimizes current master problem, requests an approximate \
        allocation based on current prices and utilities, calculates phi with current optimal values of master problem \
        and then compares this with current z value.
        :return: False if auction is done and True if a Bender's cut has been added and the auction continues.
        """
        iteration = len(self.allocations)

        self.log.log('')
        self.log.log('######## ITERATION %s ########' % iteration)

        self.optimize()
        no_change = self.old_z == self.objective and all(
            [any(old_utility == utility for old_utility in self.old_utilities) for utility in self.utilities])
        self.log.log("no change ... %s" % no_change)
        self.old_z = self.objective
        self.old_utilities = self.utilities

        # allocation := X
        allocation = self.approximator.approximate(self.price, self.utilities)

        # first_term - second_term = w*b - (c + wA) * X
        # first_term is w*b
        first_term = sum([-w * b for w, b in zip(self.utilities.values() + [self.price], self.b)])
        # second_term is (c + wA) * X
        second_term = 0
        for assignment in allocation.assignments:
            # for each x_ij which is 1 we generate c + wA which is (for MUA): v_i(j) + price * j + u_i
            second_term += self.price * assignment.quantity
            second_term += -self.utilities[assignment.agent_id]
            second_term += assignment.valuation
        phi = first_term - second_term
        self.log.log('phi = %s - %s = %s' % (first_term, second_term, phi))

        # check if phi with current result of master-problem is z (with tolerance)
        if math.fabs(phi - self.z.x) < epsilon or iteration > iteration_abort_threshold:
                self.remove_bad_cuts()
                self.set_allocation_probabilities()
                self.print_results()
                return False
        else:
            self.give_second_chance = True
            # otherwise continue and add cut based on this iteration's allocation
            allocation_name = 'X%s' % iteration
            self.allocations[allocation_name] = allocation
            self.add_benders_cut(allocation, allocation_name)
        self.set_allocation_probabilities()
        return True

    def add_price_constraint(self, new_price=None):
        if True:
            return None
        try:
            self.m.remove(self.m.getConstrByName("price_constraint"))
        except GurobiError:
            pass

        if new_price != None:
            self.old_price_constraint = new_price
        else:
            self.old_price_constraint -= .5

        self.log.log(self.old_price_constraint)
        self.m.addConstr(self.price_var, GRB.EQUAL, self.old_price_constraint, name="price_constraint")

    def print_results(self):
        """
        Prints results in console.
        """
        self.log.log('')
        self.log.log('####### SUMMARY #######')
        self.log.log('')

        self.m.write("master-program.lp")

        for item in self.allocations.iteritems():
            if item[1].probability > 0:
                # noinspection PyArgumentList
                self.log.log('%s (%s)' % (item[0], item[1].probability))
                item[1].print_me(self.log)
                self.log.log('')

        if self.price_changed:
            self.log.log('Price has decreased at some point.')
        self.log.log('%s iterations needed' % len(self.allocations))
        self.log.log('E[Social welfare] is %s' % -self.z.x)

    def optimize(self):
        """
        Optimizes current master-problem and outputs optimal values and dual variables
        """
        # for observation we save the current price
        current_price = self.price if self.price else 0.

        self.m.optimize()

        if current_price > self.price:
            self.price_changed = True

        for v in [v for v in self.m.getVars() if v.x != 0.]:
            self.log.log('%s %g' % (v.varName, v.x))

        for l in self.m.getConstrs():
            if l.Pi > 0:
                self.log.log('%s %g' % (l.constrName, l.Pi))

    def remove_bad_cuts(self):
        for l in self.m.getConstrs():
            if l.Pi == 0:
                self.m.remove(l)

    def add_benders_cut(self, allocation, name):
        """
        Adds another cut z <= wb - (c + wA) * X.
        :param allocation: Allocation as list of Assignment.
        :param name: Name for new constraint.
        """
        # wb part of cut
        expr = LinExpr(self.b, self.utility_vars.values() + [self.price_var])
        for assignment in allocation.assignments:
            # c
            expr.addConstant(-assignment.valuation)
            # if w=(u, p) then this is the uA part (for columns where X is 1)
            expr.addTerms(-1, self.utility_vars[assignment.agent_id])
            # if w=(u, p) then this is the pA part (for columns where X is 1)
            expr.addTerms(-assignment.quantity, self.price_var)
            # we get v_i(j) + u_i + j * price summed over all i,j where x_ij = 1

        self.m.addConstr(self.z, GRB.LESS_EQUAL, expr, name=name)

    def set_allocation_probabilities(self):
        for item in self.allocations.iteritems():
            # noinspection PyArgumentList
            constraint = self.m.getConstrByName(item[0])
            item[1].probability = constraint.pi if constraint else 0


class OptimalSolver:
    def __init__(self, supply, agents, gap, restriced=False):
        print ''
        print 'Optimal Solver:'

        self.m = Model("multi-unit-auction")
        self.m.params.LogToConsole = 0
        self.allocation_vars = dict()
        for agent in agents:
            for i in range(1, supply + 1):
                self.allocation_vars[agent.id, i] = self.m.addVar(lb=0., ub=1., vtype=GRB.CONTINUOUS, name='x_%s_%s' % (agent.id, i))

        self.m.update()

        for agent in agents:
            self.m.addConstr(quicksum(self.allocation_vars[agent.id, i] for i in range(1, supply + 1)), GRB.LESS_EQUAL, 1, name="u_%s" % agent.id)
            if restriced:
                for valuation in agent.valuations:
                    if valuation.valuation > 0:
                        self.m.addConstr(self.allocation_vars[agent.id, valuation.quantity] >= epsilon, name="not_zero_%s_%s" % (agent.id, valuation.quantity))


        self.m.addConstr(quicksum(self.allocation_vars[agent.id, i]*i for i in range(1, supply + 1) for agent in agents), GRB.LESS_EQUAL, supply, name="price")

        obj_expr = LinExpr()
        for agent in agents:
            for valuation in agent.valuations:
                obj_expr.addTerms(valuation.valuation, self.allocation_vars[agent.id, valuation.quantity])
        self.m.setObjective(obj_expr, GRB.MAXIMIZE)

        self.m.update()

        self.m.optimize()
        #
        # for agent in agents:
        #     for i in range(1, supply + 1):
        #         self.allocation_vars[agent.id, i] = self.m.addVar(vtype=GRB.CONTINUOUS, lb=0,
        #                                                           name='x_%s_%s' % (agent.id, i))
        #
        # self.m.update()
        #
        # self.m.addConstr(quicksum(self.allocation_vars[agent.id, i] for i in range(1, supply + 1) for agent in agents),
        #                  GRB.LESS_EQUAL, supply / gap, name="price")
        # for agent in agents:
        #     for i in range(1, supply):
        #         self.m.addConstr(self.allocation_vars[agent.id, i + 1] - self.allocation_vars[agent.id, i],
        #                          GRB.LESS_EQUAL, 0, name="chain_%s_%s" % (agent.id, i))
        #         self.m.addConstr(self.allocation_vars[agent.id, i], GRB.LESS_EQUAL, 1. / gap,
        #                          name="p_%s_%s" % (agent.id, i))
        #     self.m.addConstr(self.allocation_vars[agent.id, supply], GRB.GREATER_EQUAL, 0, name="greater_%s" % agent.id)
        #     self.m.addConstr(self.allocation_vars[agent.id, 1], GRB.LESS_EQUAL, 1. / gap, name="u_%s" % agent.id)
        #
        # # m.addConstr(x11 + 2*x12 + 3*x13 + 4*x14 + x21 + 2*x22 + 3*x23 + 4*x24, GRB.LESS_EQUAL, 4, name="p_an")
        #
        # obj_expr = LinExpr()
        # for agent in agents:
        #     prev_val = None
        #     for valuation in agent.valuations:
        #         try:
        #             prev_val = next(val for val in agent.valuations if val.quantity == valuation.quantity - 1)
        #         except StopIteration:
        #             pass
        #         marginal_value = valuation.valuation - (prev_val.valuation if prev_val else 0)
        #         obj_expr.addTerms(marginal_value, self.allocation_vars[agent.id, valuation.quantity])
        # self.m.setObjective(obj_expr, GRB.MAXIMIZE)
        #
        # self.m.optimize()

        for v in [v for v in self.m.getVars() if v.x != 0.]:
            print('%s %g' % (v.varName, v.x))

        print ''
        print 'CONSTRAINTS:'

        for l in self.m.getConstrs():
            if l.Pi > 0:
                print('%s %g' % (l.constrName, l.Pi))

        print self.m.getObjective().getValue()

        # print 'Optimal solution:'
        # for v in self.m.getVars():
        #     print('%s %g' % (v.varName, v.x))
        # for l in self.m.getConstrs():
        #     if l.Pi > 0:
        #         print('%s %g' % (l.constrName, l.Pi))
        print 'OPT social welfare %s | %s/%s=%s' % (
        self.m.getObjective().getValue(), self.m.getObjective().getValue(), gap,
        self.m.getObjective().getValue() / gap)

        self.m.write('optimal-lp.lp')
        self.m.write('optimal-lp.sol')

class NisanGreedyDemandApproximator:
    def __init__(self, supply, agents, log):
        self.supply = supply
        self.agents = agents
        self.log = log

    @property
    def gap(self):
        return 2.

    def approximate(self, price, utilities):
        allocation = Allocation()
        for agent in self.agents:
            demand = agent.query_demand(price, self.supply, utilities[agent.id])
            if demand:
                allocation.assignments += [Assignment(demand.quantity, agent.id, demand.valuation)]

        allocation.print_me(self.log)

        return allocation

class LaviSwamyGreedyApproximator:
    def __init__(self, supply, agents, log):
        """
        :param supply: Supply up for auction.
        :param agents: List of Agent.
        """
        self.supply = supply
        self.agents = agents
        self.log = log

    @property
    def gap(self):
        """
        :return: Returns approximation gap for this algorithm.
        """
        return 2.

    def approximate(self, price, utilities):
        """
        Approximates on current price and utilities vector
        :param price: Current price.
        :param utilities: Dict of utilities for each agent (agent_id being the key).
        :return:
        """
        allocation = self.allocate(self.agents[:], price, utilities)

        allocation.print_me(self.log)

        return allocation

    def allocate(self, agents, price, utilities):
        left_supply = self.supply
        assignments = [Assignment(0, agent.id, 0) for agent in agents]
        # as done in Lavi & Swamy 2005 mostly
        margin = 0
        while left_supply > 0 and left_supply - margin >= 0:
            query_responses = dict()
            per_item_utilities = dict()

            # ask each agent for his demand at current price.
            for agent in agents:
                assignment = next(assignment for assignment in assignments if assignment.agent_id == agent.id)
                marginal_value = agent.marginal_value_query(margin, assignment.quantity)
                # if there is demand we add the agent's per_item_value to possible selection.
                if marginal_value != None:
                    # denominator is calculated with utility subtracted as it would have been done if we calculated
                    # the c vector as done in Fadaei 2015
                    marginal_utility = marginal_value - utilities[agent.id] - (assignment.quantity + margin) * price
                    # print '%s - %s - %s * %s' % (demand.valuation, utilities[agent.id], demand.quantity, price)
                    if marginal_utility > 0. and assignment.quantity + margin > 0:
                        per_item_utilities[agent.id] = marginal_utility / (assignment.quantity + margin)
                        query_responses[agent.id] = marginal_value

            # if there was any demand we look for the agent with the maximal per-item-value
            if per_item_utilities:
                best_agent_id = max(per_item_utilities.iterkeys(),
                                    key=(lambda key: per_item_utilities[key]))

                # we allocate the items to the agent, therefore we remove these from the supply
                left_supply -= margin
                assignments = [assignment if
                               assignment.agent_id != best_agent_id else
                               Assignment(assignment.quantity + margin, best_agent_id, assignment.valuation + query_responses[best_agent_id]) for assignment in assignments]
            else:
                margin += 1

        allocation = Allocation([assignment for assignment in assignments if assignment.quantity > 0])
        summed_valuations = sum(assignment.valuation for assignment in assignments)

        # check if assigning all items to one agent is better
        for agent in agents:
            marginal_value = agent.query_value(self.supply)
            if marginal_value.valuation - utilities[agent.id] - marginal_value.quantity * price > summed_valuations:
                summed_valuations = marginal_value.valuation
                allocation = Allocation([Assignment(self.supply, agent.id, marginal_value.valuation)])

        return allocation
