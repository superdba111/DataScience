#list1 = [expression for i in iterable if condition]
#dict1 = {key:value for i in iterable if condition}
#set1 = {value for i in iterable if condition}

l1 = [i for i in range(1,4)]              # [1,2,3]
l2 = [i*2 for i in range(1,4)]            # [2,4,6]
l3 = [i**2 for i in range(1,4)]           # [1,4,9]
l4 = [i for i in range(1,4) if i%2==1]    # [1,3]
