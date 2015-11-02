from gurobipy.gurobipy import Model, GRB

__author__ = 'Usiel'

m = Model("play")

x11 = m.addVar(vtype=GRB.CONTINUOUS, name="x11", lb=0)
x12 = m.addVar(vtype=GRB.CONTINUOUS, name="x12")
x13 = m.addVar(vtype=GRB.CONTINUOUS, name="x13")
x14 = m.addVar(vtype=GRB.CONTINUOUS, name="x14")
x21 = m.addVar(vtype=GRB.CONTINUOUS, name="x21")
x22 = m.addVar(vtype=GRB.CONTINUOUS, name="x22")
x23 = m.addVar(vtype=GRB.CONTINUOUS, name="x23")
x24 = m.addVar(vtype=GRB.CONTINUOUS, name="x24")

m.update()

m.addConstr(x11 + x12 + x13 + x14 + x21 + x22 + x23 + x24, GRB.LESS_EQUAL, 2, name="all")
m.addConstr(x12, GRB.LESS_EQUAL, x11, name="c11")
m.addConstr(x13, GRB.LESS_EQUAL, x12, name="c12")
m.addConstr(x14, GRB.LESS_EQUAL, x13, name="c13")
m.addConstr(x22, GRB.LESS_EQUAL, x21, name="c21")
m.addConstr(x23, GRB.LESS_EQUAL, x22, name="c22")
m.addConstr(x24, GRB.LESS_EQUAL, x23, name="c23")
m.addConstr(x14, GRB.GREATER_EQUAL, 0, name="11")
m.addConstr(x24, GRB.GREATER_EQUAL, 0, name="12")
m.addConstr(x11, GRB.LESS_EQUAL, .5, name="u1")
m.addConstr(x21, GRB.LESS_EQUAL, .5, name="u2")
#m.addConstr(x11 + 2*x12 + 3*x13 + 4*x14 + x21 + 2*x22 + 3*x23 + 4*x24, GRB.LESS_EQUAL, 4, name="p_an")

m.setObjective(x11 * 6 + x12 * 0 + x13 * 0 + x14 * 3 + x21 * 1 + x22 * 3 + x23 * 0 + x24 * 2, GRB.MAXIMIZE)



m.optimize()

for v in [v for v in m.getVars() if v.x != 0.]:
    print('%s %g' % (v.varName, v.x))

print 'CONSTRS'

for l in m.getConstrs():
    if l.Pi > 0:
        print('%s %g' % (l.constrName, l.Pi))

print m.getObjective().getValue()