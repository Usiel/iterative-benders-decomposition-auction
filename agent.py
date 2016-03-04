import itertools
import math
import pprint

import numpy as np
from common import Valuation, epsilon

__author__ = 'Usiel'


def next_agent_id():
    next_agent_id.counter += 1
    return next_agent_id.counter


next_agent_id.counter = 0


class ManualAgent:
    def __init__(self, valuations, identifier=None):
        """
        :param valuations: List of Valuation.
        :param identifier: Optional identifier (unique).
        """
        self.id = identifier if identifier >= 0 else next_agent_id()
        self.valuations = valuations
        # print 'Agent %s:' % self.id
        # for v in self.valuations:
        #     print 'v(%s)=%s' % (v.quantity, v.valuation)
        self.queried = []

    def query_demand(self, price, left_supply, base_price):
        if (price, left_supply) not in self.queried:
            self.queried += [(price, left_supply)]

        best_valuation = None
        best_utility = None
        for valuation in self.valuations:
            if valuation.quantity <= left_supply:
                utility = (self.calculate_utility(price, valuation))
                if utility >= -epsilon and utility >= best_utility:
                    best_valuation = valuation
                    best_utility = utility
        return best_valuation

    def query_relative_demand(self, price, left_supply, base_price):
        """
        Returns quantity and valuation for this quantity, which maximizes the agent's utility. \
        Real demand query would only return j. We can however simulate a value query for j with mt demand queries.
        :param price: Current price-per-item.
        :param left_supply: Supply available at the moment.
        :return: Returns Valuation if utility > 0, else None.
        """
        if (price, left_supply) not in self.queried:
            self.queried += [(price, left_supply)]

        best_valuation = None
        best_utility = None
        for valuation in self.valuations:
            if valuation.quantity <= left_supply:
                utility = (self.calculate_utility(price, valuation)) / valuation.quantity
                if utility > 0 and utility >= best_utility:
                    best_valuation = valuation
                    best_utility = utility
        return best_valuation

    def query_relative_marginal_demand(self, price, quantity_owned, left_supply):
        pass

    def marginal_value_query(self, additional_quantity, quantity_owned):
        quantity_owned_value = next(valuation.valuation for valuation in self.valuations if
                                    valuation.quantity == quantity_owned) if quantity_owned > 0 else 0.
        try:
            combined_quantity_value = next(valuation.valuation for valuation in self.valuations if
                                           valuation.quantity == quantity_owned + additional_quantity)
        except StopIteration:
            combined_quantity_value = 0.
        return combined_quantity_value - quantity_owned_value

    def query_value(self, quantity):
        """
        Returns valuation for a certain quantity. Should be simulated by demand queries at later stage.
        :param quantity: Quantity we want to know valuation for.
        :return: Returns Valuation or None (if not defined).
        """
        valuation = itertools.ifilter(lambda x: x.quantity == quantity, self.valuations).next()
        if valuation:
            return valuation
        return None

    def introduce_yourself(self):
        print 'I am Agent %s' % self.id
        for valuation in self.valuations:
            print 'v(%s)=%s | ' % (valuation.quantity, valuation.valuation),
        print ''
        print ''

    def query_demand_set(self, price, left_supply):
        valid_valuations = [valuation for valuation in self.valuations if valuation.quantity <= left_supply]
        max_valuations = {valuation for valuation in valid_valuations
                          if (self.calculate_utility(price, valuation)) + epsilon >= max(
            (self.calculate_utility(price, v)) for v in valid_valuations) and self.calculate_utility(price, valuation) + epsilon >= 0}
        return max_valuations

    def calculate_utility(self, price, valuation):
        return valuation.valuation - valuation.quantity * price


class RandomizedAgent(ManualAgent):
    def __init__(self, supply, identifier=None):
        """
        RandomizedAgent uses a distribution to pick random valuations. v_i(j) is non-decreasing for increasing j.
        :param supply: Supply available in auction (needed for valuation generation).
        :param identifier: Optional identifier (unique).
        """
        valuations = []
        for i in range(1, supply + 1):
            previous_valuation = 0
            if i > 1:
                previous_valuation = valuations[i - 2].valuation
            valuations.append(Valuation(i, math.floor(previous_valuation + np.random.exponential(5.0))))

        ManualAgent.__init__(self, valuations, identifier)


def generate_randomized_agents(supply, agents_count):
    """
    Generates randomized agents.
    :param supply: Supply up for auction.
    :param agents_count: Agents to generate.
    :return:
    """
    agents = [RandomizedAgent(supply) for i in range(0, agents_count)]
    for agent in agents:
        agent.introduce_yourself()
    return agents
