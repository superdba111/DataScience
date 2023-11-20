class Dog:
  # behaviour when Dog object is created
  def __init__(self, name, age):
    self.name = name
    self.age = age

  # behaviour when str(dog_object) is called
  def __str__(self):
    return f'Dog({self.name}, {self.age})'

  # behaviour when dog1 == dog2 happens
  def __eq__(self, otherDog):
    return self.name == otherDog.name and self.age == otherDog.age


'''
Magic methods usually start with 2 underscores, and also end with 2 underscores. They allow us to define special behaviour in our objects.
The __init__ magic method defines how our Dog object is initialized
The __str__ magic method defines what is returned when str(dog_object) is called, or when print(dog_object) is called
The __eq__ magic method defines what happens when we attempt to compare 2 dog objects using dog1 == dog2
'''
