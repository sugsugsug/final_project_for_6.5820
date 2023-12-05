class Job():
  def __init__(self, total_time, com_list):
    self.total_time=total_time
    # start and end of job must differ in state
    self.com_list=com_list # [[start_time_1,end_time_1],[start_time_2,end_time_2]]
    self.pos = 0
  
  def next(self, quota):
    pos = self.pos
    a=0
    b=-1
    for i in range(len(self.com_list)):
      if pos < self.com_list[i][0]:
        a=i
        b=0
        break
      if pos < self.com_list[i][1]:
        a=i
        b=1
        break
    t=0
    if b==-1:
      t=(self.total_time-pos)/quota
    else:
      t=(self.com_list[a][b]-pos)/quota
    return t
    # t is the actual time spent in the real world

  def move(self, quota, t):
    pos = self.pos
    pos = pos + t*quota
    if pos > self.total_time:
      print('err')
      exit(1)
    elif pos == self.total_time:
      self.pos = 0
    else:
      self.pos = pos

j1=Job(20, [[10,20]])
j2=Job(5, [[3,5]])
len_gen = 30

class TernaryTree():
  def __init__(self, pos1, pos2, time_spent, num_success):
    self.pos1=pos1
    self.pos2=pos2
    self.time_spent=time_spent
    self.num_success=num_success
  
  def branching(self):
    if self.time_spent > len_gen:
# -1 means the last of the sequence of options we should pick
      return self.num_success, [-1]
    else:
      nc_cand=[0,0,0]
      l_cand=[[],[],[]]
      # 1:0
      j1.pos = self.pos1
      t=j1.next(1)
      j1.move(1,t)
      print('0: ', self.pos1, j1.pos)
      if j1.pos < self.pos1:
        nc_cand[0] = 1
      tree = TernaryTree(j1.pos,self.pos2,self.time_spent+t,self.num_success+nc_cand[0])
      nc_cand[0], l_cand[0] = tree.branching()

      # 0.5:0.5
      j1.pos = self.pos1
      j2.pos = self.pos2
      t1=j1.next(0.5)
      t2=j2.next(0.5)

      t=t2
      if t1<t2:
        t=t1
      j1.move(0.5,t)
      j2.move(0.5,t)
      print('1: ', self.pos1, j1.pos)
      print('1: ', self.pos2, j2.pos)

      if j1.pos < self.pos1:
        nc_cand[1] = nc_cand[1]+1
      if j2.pos < self.pos2:
        nc_cand[1] = nc_cand[1]+1
      tree = TernaryTree(j1.pos,j2.pos,self.time_spent+t,self.num_success+nc_cand[1])
      nc_cand[1], l_cand[1] = tree.branching()

      # 0:1
      j2.pos = self.pos2
      t=j2.next(1)
      j2.move(1,t)
      print('2: ', self.pos2, j2.pos)
      if j2.pos < self.pos2:
        nc_cand[2] = 1
      tree = TernaryTree(self.pos1,j2.pos,self.time_spent+t,self.num_success+nc_cand[2])
      nc_cand[2], l_cand[2] = tree.branching()

      index, max_val = -1, -1
      for i in range(len(nc_cand)):
        if nc_cand[i] > max_val:
          index, max_val = i, nc_cand[i]
      return max_val, [index] + l_cand[index]


options=[]

main_tree=TernaryTree(0,0,0,0)
print(main_tree.branching())


