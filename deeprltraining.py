import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F

class PolicyNetwork(nn.Module):
    def __init__(self, input_size, hidden_size, output_size):
        super(PolicyNetwork, self).__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return F.softmax(x, dim=-1)

class TestCasePrioritizationEnvironment:
    def __init__(self, test_cases, costs, value_priorities, historical_success_rates):
        self.test_cases = test_cases
        self.costs = costs
        self.value_priorities = value_priorities
        self.historical_success_rates = historical_success_rates
        self.state = np.zeros(len(test_cases))  # Initial state
        self.total_cost = 0
        self.selected_test_cases_sequence = []  # Store selected test cases for each episode

    def step(self, action):
        # Convert action tensor to scalar
        action_scalar = action.item()

        # Execute selected test cases
        selected_test_cases = [self.test_cases[i] for i in range(len(self.test_cases)) if action_scalar == 1]
        executed_test_cases_cost = sum(self.costs[test_case] for test_case in selected_test_cases)
        self.total_cost += executed_test_cases_cost
        
        # Calculate reward based on value priority and historical success rate
        reward = sum(self.value_priorities[test_case] * self.historical_success_rates[test_case]
                     for test_case in selected_test_cases)
        
        # Update state
        self.state = np.zeros(len(self.test_cases))  # Reset state
        for i in range(len(self.test_cases)):
            if self.test_cases[i] in selected_test_cases:
                self.state[i] = 1
        
        # Store selected test cases for this episode
        self.selected_test_cases_sequence.append(selected_test_cases)
        
        return self.state, reward, self.total_cost

    def reset(self):
        self.state = np.zeros(len(self.test_cases))  # Reset state
        self.total_cost = 0
        return self.state

# Usage
df = pd.read_excel('data_input.xlsx')
test_cases = df['Test Cases'].tolist()
costs = df.set_index('Test Cases')['Cost'].to_dict()
value_priorities = df.set_index('Test Cases')['Value Priorities'].to_dict()
historical_success_rates = df.set_index('Test Cases')['Historical Success Rate'].to_dict()

env = TestCasePrioritizationEnvironment(test_cases, costs, value_priorities, historical_success_rates)

# Deep RL training loop
input_size = len(test_cases)
hidden_size = 128
output_size = len(test_cases)
policy_net = PolicyNetwork(input_size, hidden_size, output_size)
optimizer = optim.Adam(policy_net.parameters(), lr=0.001)
gamma = 0.99  # Discount factor
num_episodes = 100
max_steps_per_episode = 100

for episode in range(num_episodes):
    state = env.reset()
    episode_log_probs = []
    episode_rewards = []
    for step in range(max_steps_per_episode):
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        action_probs = policy_net(state_tensor)
        action_dist = torch.distributions.Categorical(action_probs)
        action = action_dist.sample().item()  # Convert tensor to scalar
        action_tensor = torch.tensor([action])  # Convert scalar to tensor
        episode_log_probs.append(action_dist.log_prob(action_tensor))  # Pass action tensor
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

# Print sequence of selected test cases
print("Final Result - Sequence of Selected Test Cases:")
for i, selected_test_cases in enumerate(env.selected_test_cases_sequence, start=1):
    print("Episode", i, ":", selected_test_cases)