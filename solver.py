import math

from gurobipy.gurobipy import Model, GRB, LinExpr, GurobiError, quicksum

from common import Assignment, epsilon, Allocation

__author__ = 'Usiel'


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
        self.m.setObjective(self.z, GRB.MAXIMIZE)

        self.price_changed = False

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
        if math.fabs(phi - self.z.x) < epsilon:
            self.remove_bad_cuts()
            self.optimize()
            self.set_allocation_probabilities()
            self.print_results()
            return False
        # otherwise continue and add cut based on this iteration's allocation
        else:
            allocation_name = 'X%s' % iteration
            self.allocations[allocation_name] = allocation
            self.add_benders_cut(allocation, allocation_name)
            return True

    def print_results(self):
        """
        Prints results in console.
        """
        self.log.log('')
        self.log.log('####### SUMMARY #######')
        self.log.log('')

        self.m.write("master-program.lp")

        for item in self.allocations.iteritems():
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
    def __init__(self, supply, agents, gap):
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
            self.m.addConstr(quicksum(self.allocation_vars[agent.id, i] for i in range(1, supply + 1)), GRB.LESS_EQUAL, 1)

        self.m.addConstr(quicksum(self.allocation_vars[agent.id, i]*i for i in range(1, supply + 1) for agent in agents), GRB.LESS_EQUAL, supply)

        obj_expr = LinExpr()
        for agent in agents:
            for valuation in agent.valuations:
                obj_expr.addTerms(valuation.valuation, self.allocation_vars[agent.id, valuation.quantity])
        self.m.setObjective(obj_expr, GRB.MAXIMIZE)

        self.m.update()

        self.m.optimize()
        # print 'Optimal solution:'
        # for v in self.m.getVars():
        #     print('%s %g' % (v.varName, v.x))
        # for l in self.m.getConstrs():
        #     if l.Pi > 0:
        #         print('%s %g' % (l.constrName, l.Pi))
        print 'OPT social welfare %s | %s/%s=%s' % (self.m.getObjective().getValue(), self.m.getObjective().getValue(), gap, self.m.getObjective().getValue()/gap)

        self.m.write('optimal-lp.lp')
        self.m.write('optimal-lp.sol')


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
        allocation = Allocation()
        agents_pool = agents[:]
        summed_valuations = 0
        demands = dict()
        # as done in Lavi & Swamy 2005 mostly
        while agents_pool and left_supply > 0:
            query_responses = dict()
            per_item_values = dict()

            # ask each agent for his demand at current price.
            for agent in agents_pool:
                demand = agent.query_demand(price, left_supply)
                # if there is demand we add the agent's per_item_value to possible selection.
                if demand:
                    # denominator is calculated with utility subtracted as it would have been done if we calculated
                    # the c vector as done in Fadaei 2015
                    new_utility = demand.valuation - utilities[agent.id] - demand.quantity * price
                    if new_utility > epsilon:
                        per_item_values[agent.id] = new_utility / demand.quantity
                        query_responses[agent.id] = demands[agent.id] = demand

            # if there was any demand we look for the agent with the maximal per-item-value
            if per_item_values:
                best_agent_id = max(per_item_values.iterkeys(),
                                    key=(lambda key: per_item_values[key]))

                # we allocate the items to the agent, therefore we remove these from the supply
                left_supply -= query_responses[best_agent_id].quantity
                # maybe check if this is valid?
                agents_pool = [agent for agent in agents_pool if agent.id != best_agent_id]

                allocation.append(Assignment(query_responses[best_agent_id].quantity,
                                             best_agent_id,
                                             query_responses[best_agent_id].valuation))
                summed_valuations += query_responses[best_agent_id].valuation - utilities[
                    best_agent_id] - price * query_responses[best_agent_id].quantity
            else:
                break

        # check if assigning all items to one agent is better
        for agent in agents:
            valuation = agent.query_value(self.supply)
            if valuation.valuation - utilities[agent.id] - self.supply * price > summed_valuations:
                summed_valuations = valuation.valuation
                allocation = Allocation([Assignment(self.supply, agent.id, valuation.valuation)])

        return allocation
