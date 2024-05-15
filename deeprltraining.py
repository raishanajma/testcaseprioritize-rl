import seed_drl
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F

#default cost for missing test cases
DEFAULT_COST_VALUE = 0

class PolicyNetwork(nn.Module): #neural network block
    def __init__(self, input_size, hidden_size, output_size):
        super(PolicyNetwork, self).__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return F.softmax(x, dim=-1)

class TestCasePrioritizationEnvironment: #environment where agent interacts
    def __init__(self, test_cases, costs, value_priorities, complexities):
        self.test_cases = test_cases #test case ID
        self.costs = costs #attribute
        self.value_priorities = value_priorities #attribute
        self.complexities = complexities #attribute
        self.state = np.zeros(len(test_cases))  #initial state
        self.total_cost = 0
        self.selected_test_cases_sequences = []  #store selected test cases for each episode

    def step(self, action):
        #convert action tensor to scalar
        action_scalar = action.item()

        #execute selected test cases
        selected_test_case = self.test_cases[action_scalar]
        
        #get the cost for the selected test case
        executed_test_case_cost = self.costs.get(selected_test_case, DEFAULT_COST_VALUE)
        self.total_cost += executed_test_case_cost
        
        #calculate reward based on value priority and complexity
        reward = (4 - self.value_priorities[selected_test_case]) * self.complexities[selected_test_case]
        
        #update state
        self.state = np.zeros(len(self.test_cases))  #reset state
        self.state[action_scalar] = 1
        
        #store selected test case for this step
        self.selected_test_cases_sequences[-1].append(selected_test_case)
        
        return self.state, reward, self.total_cost

    def reset(self):
        self.state = np.zeros(len(self.test_cases))  #reset state
        self.total_cost = 0
        self.selected_test_cases_sequences.append([])  #start new episode
        return self.state

#implement
df = pd.read_excel('Test_Project_MIS.xlsx')
test_cases = df['Test Cases'].tolist()
costs = df.set_index('Test Cases')['Cost'].to_dict()
value_priorities = df.set_index('Test Cases')['Weights'].to_dict()
complexities = df.set_index('Test Cases')['Complexity'].to_dict()

for key, value in value_priorities.items():
    if value == 1:
        value_priorities[key] = 3
    elif value == 3:
        value_priorities[key] = 1

env = TestCasePrioritizationEnvironment(test_cases, costs, value_priorities, complexities)

#deep RL training loop
input_size = len(test_cases)
hidden_size = 128 #the number of neurons or units in the hidden layer of the network
output_size = len(test_cases)
policy_net = PolicyNetwork(input_size, hidden_size, output_size)
optimizer = optim.Adam(policy_net.parameters(), lr = 0.001)
gamma = 0.99  #discount factor
num_episodes = 100
max_steps_per_episode = len(test_cases)

for episode in range(num_episodes):
    state = env.reset()
    episode_log_probs = []
    episode_rewards = []
    for step in range(max_steps_per_episode): 
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        action_probs = policy_net(state_tensor)
        action_dist = torch.distributions.Categorical(action_probs)
        action = action_dist.sample().item()  #convert tensor to scalar
        action_tensor = torch.tensor([action])  #convert scalar to tensor
        episode_log_probs.append(action_dist.log_prob(action_tensor))  #pass action tensor
        next_state, reward, total_cost = env.step(action_tensor)
        episode_rewards.append(reward)
        state = next_state
    returns = []
    R = 0
    for r in episode_rewards[::-1]:
        R = r + gamma * R
        returns.insert(0, R)
    returns = torch.tensor(returns)
    episode_log_probs = torch.stack(episode_log_probs)
    policy_loss = (-episode_log_probs * returns).sum()
    optimizer.zero_grad()
    policy_loss.backward()
    optimizer.step()

#print sequence of test cases for each episode
print("Final Result - Sequence of Selected Test Cases:")
for i, selected_test_cases in enumerate(env.selected_test_cases_sequences, start = 1):
    print("Episode", i, ":", selected_test_cases, "\n")