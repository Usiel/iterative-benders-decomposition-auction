__author__ = 'Usiel'


class Valuation:
    def __init__(self, quantity, valuation):
        """
        :param quantity: Quantity valued by this Valuation.
        :param valuation: Number representing valuation for quantity.
        """
        self.quantity = quantity
        self.valuation = valuation


class Assignment:
    def __init__(self, quantity, agent_id, valuation):
        """
        :param quantity: Quantity assigned to agent.
        :param agent_id: Agent identifier this assignment concerns.
        :param valuation: Valuation (number) agent has for quantity.
        """
        self.quantity = quantity
        self.agent_id = agent_id
        self.valuation = valuation

    def print_me(self):
        """
        Prints out assignment to console.
        """
        print 'Agent %s receives %s item(s) (v_%s(%s)=%s)' % \
              (self.agent_id, self.quantity, self.agent_id, self.quantity, self.valuation)

epsilon = 1e-3
