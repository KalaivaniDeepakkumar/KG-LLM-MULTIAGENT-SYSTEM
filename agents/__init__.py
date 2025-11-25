"""
Multi-Agent System for Agricultural Residue Allocation

This package contains specialized agents for creating and optimizing
residue allocation plans:

- PlannerAgent: Creates initial allocation plans based on inputs and constraints
- OptimizerAgent: Refines and optimizes plans for maximum efficiency and sustainability
"""

from .planner_agent import PlannerAgent
from .optimizer_agent import OptimizerAgent

__all__ = ['PlannerAgent', 'OptimizerAgent']

