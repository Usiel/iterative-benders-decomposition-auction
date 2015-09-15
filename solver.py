import math

from gurobipy.gurobipy import Model, GRB, LinExpr

from common import Assignment, epsilon

__author__ = 'Usiel'


class BendersSolver:
    def __init__(self, b, agents):
        """
        :param b: b of LP. If n=len(agents) then the first n values are 1./alpha and n+1 value is supply/alpha.
        :param agents: List of agents.
        """
        # Setting up master problem
        self.m = Model("master-problem")
        # noinspection PyArgumentList,PyArgumentList,PyArgumentList
        self.z = self.m.addVar(lb=-GRB.INFINITY, ub=GRB.INFINITY, name="z")
        self.b = b
        self.agents = agents

        self.price_var = dict()
        # noinspection PyArgumentList,PyArgumentList,PyArgumentList
        self.price_var = self.m.addVar(lb=-GRB.INFINITY, ub=0, name="price")
        self.utilityVars = dict()
        for agent in self.agents:
            # noinspection PyArgumentList,PyArgumentList,PyArgumentList
            self.utilityVars[agent.id] = self.m.addVar(lb=-GRB.INFINITY, ub=0, name="u_%s" % agent.id)

        self.m.update()

        # Initial constraints for empty allocation
        self.m.addConstr(self.z, GRB.LESS_EQUAL, LinExpr(self.b, self.utilityVars.values() + [self.price_var]),
                         name="X0")
        self.m.setObjective(self.z, GRB.MAXIMIZE)

    @property
    def price(self):
        """
        :return: Returns current price (positive).
        """
        return math.fabs(self.price_var.x)

    @property
    def utilities(self):
        """
        :return: Returns current utilities (positive): dict(agent_id: utility)
        """
        return dict((v[0], math.fabs(v[1].x)) for v in self.utilityVars.iteritems())

    def optimize(self):
        """
        Optimizes current master-problem and outputs optimal values and dual variables
        """
        self.m.optimize()
        for v in self.m.getVars():
            print('%s %g' % (v.varName, v.x))

        for l in self.m.getConstrs():
            if l.Pi > 0:
                print('%s %g' % (l.constrName, l.Pi))

    def add_benders_cut(self, allocation, name):
        """
        Adds another cut z <= wb - (c + wA) * X.
        :param allocation: Allocation as list of Assignment.
        :param name: Name for new constraint.
        """
        # wb part of cut
        expr = LinExpr(self.b, self.utilityVars.values() + [self.price_var])
        for a in allocation:
            # c
            expr.addConstant(-a.valuation)
            # if w=(u, p) then this is the uA part (for columns where X is 1)
            expr.addTerms(-1, self.utilityVars[a.agent_id])
            # if w=(u, p) then this is the pA part (for columns where X is 1)
            expr.addTerms(-a.quantity, self.price_var)
            # we get v_i(j) + u_i + j * price summed over all i,j where x_ij = 1

        self.m.addConstr(self.z, GRB.LESS_EQUAL, expr, name=name)


class LaviSwamyGreedyApproximator:
    def __init__(self, supply, agents):
        """
        :param supply: Supply up for auction.
        :param agents: List of Agent.
        """
        self.supply = supply
        self.agents = agents

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
        left_supply = self.supply
        agents_pool = self.agents[:]
        allocation = []
        summed_valuations = 0

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
                        query_responses[agent.id] = demand

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
        for agent in self.agents:
            valuation = agent.query_value(self.supply)
            if valuation.valuation - utilities[agent.id] - self.supply * price > summed_valuations:
                summed_valuations = valuation.valuation
                allocation = [Assignment(self.supply, agent.id, valuation.valuation)]

        for assignment in allocation:
            assignment.print_me()

        return allocation
