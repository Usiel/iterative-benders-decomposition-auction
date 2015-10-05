import itertools
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

    def query_demand(self, price, left_supply, base_price):
        """
        Returns quantity and valuation for this quantity, which maximizes the agent's utility. \
        Real demand query would only return j. We can however simulate a value query for j with mt demand queries.
        :param price: Current price-per-item.
        :param left_supply: Supply available at the moment.
        :return: Returns Valuation if utility > 0, else None.
        """
        best_valuation = None
        best_utility = None
        for valuation in self.valuations:
            if valuation.quantity <= left_supply:
                utility = (valuation.valuation - valuation.quantity * price + base_price)
                if utility >= -epsilon and utility >= best_utility:
                    best_valuation = valuation
                    best_utility = utility
        return best_valuation

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
            valuations.append(Valuation(i, previous_valuation + np.random.exponential(5.0)))

        ManualAgent.__init__(self, valuations, identifier)


def generate_randomized_agents(supply, agents_count):
    """
    Generates randomized agents.
    :param supply: Supply up for auction.
    :param agents_count: Agents to generate.
    :return:
    """
    return [RandomizedAgent(supply) for i in range(0, agents_count)]
