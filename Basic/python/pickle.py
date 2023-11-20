# saving a list into a .sav file
import pickle

lis = [4,5,6]
with open('test.sav', 'wb') as f:
  pickle.dump(lis, f)

'''
this will actually create a new file test.sav
this test.sav file will contain the list [4,5,6]
'''

# loading data from test.sav
import pickle

with open('test.sav', 'rb') as f:
  x = pickle.load(f)

print(x)    # [4,5,6]
