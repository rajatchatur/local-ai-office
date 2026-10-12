from typing import Dict

from backend.agents.base_agent import BaseAgent


class AgentRegistry:

    def __init__(self):

        self.agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent):

        if agent.name in self.agents:

            raise ValueError(
                f"Agent '{agent.name}' already exists."
            )

        self.agents[agent.name] = agent

    def remove(self, agent_name: str):

        if agent_name not in self.agents:

            raise ValueError(
                f"Agent '{agent_name}' does not exist."
            )

        del self.agents[agent_name]

    def get(self, agent_name: str):

        return self.agents.get(agent_name)

    def list_agents(self):

        return list(self.agents.values())

    def has_agent(self, agent_name: str):

        return agent_name in self.agents

    def get_agent_names(self):

        return list(self.agents.keys())

    def get_agent_info(self):

        return [
            agent.get_info()
            for agent in self.agents.values()
        ]