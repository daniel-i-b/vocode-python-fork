class LyngoChatGPTAgentRegistry:
    _agents = {}

    @classmethod
    def register_agent(cls, agent):
        """Register an instance of LyngoChatGPTAgent with its conversation_id."""
        cls._agents[agent.agent_config.conversation_id] = agent

    @classmethod
    def get_agent(cls, conversation_id):
        """Retrieve an existing LyngoChatGPTAgent instance by conversation_id."""
        return cls._agents.get(conversation_id, None)

    @classmethod
    def remove_agent(cls, conversation_id):
        """Remove an agent instance from the registry."""
        if conversation_id in cls._agents:
            del cls._agents[conversation_id]
