import math

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

    def print_me(self, log):
        """
        Prints out assignment to console.
        """
        log.log('Agent %s receives %s item(s) (v_%s(%s)=%s)' % \
              (self.agent_id, self.quantity, self.agent_id, self.quantity, self.valuation))


class Allocation:
    def __init__(self, assignments=None, probability=None):
        if not assignments:
            assignments = []
        self.assignments = assignments
        self.probability = probability

    @property
    def expected_social_welfare(self):
        if not self.probability:
            return 0
        return sum([assignment.valuation for assignment in self.assignments]) * self.probability

    def get_expected_social_welfare_without_agent(self, agent_id_to_exclude):
        if not self.probability:
            return 0
        return sum([assignment.valuation for assignment in self.assignments if assignment.agent_id!=agent_id_to_exclude]) * self.probability

    def append(self, assignment):
        self.assignments.append(assignment)

    def print_me(self, log):
        for assignment in self.assignments:
            assignment.print_me(log)


class BlackHoleLogger:
    def __init__(self):
        pass

    def log(self, message):
        pass


class ConsoleLogger:
    def __init__(self):
        pass

    def log(self, message):
        print message

epsilon = 1e-3
