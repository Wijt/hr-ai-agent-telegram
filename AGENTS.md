
This document defines senior engineering principles, system design rules, and agent execution guidelines. It contains no code or implementation details.

## 1. Core Engineering Principles

Apply these principles to all development tasks. Read these principles before you write code.

### Keep It Simple

* Simple means consistent.
* Do not build two separate architectures. Two architectures increase maintenance work and introduce inconsistent patterns.
* Follow the official patterns of the framework.

### Add Complexity Step by Step

* Do not design a system for all future needs at the start.
* Begin with the simplest working version.
* Verify that the current layer works before you add the next layer.

### Start with a Working Minimum Skeleton
* Write the smallest end-to-end working system first.

### Follow Official Best Practices

* Search and read the official framework documentation before you write code.
* Follow the official examples and patterns closely.
* Do not deviate from established patterns without a clear reason.

### Ask Before You Deviate

* If you must deviate from a best practice, explain the concrete reason to the user first.
* Obtain explicit approval from the user before you implement a non-standard design.

---

## 2. System Design Principles
### Context Optimization

* Do not send raw file content into the main model context.
* Store raw files for tool access only.
* Pass structured data between workflow steps to keep model execution predictable.

---

## 3. Pre-Action Checklist for AI Agents

Complete these steps before you perform any task:

1. **Review core principles.**
Check Section 1 of this document before you write or modify code.
2. **Verify official documentation.**
If you use framework features, search the official documentation for recommended patterns. ALWAYS think what could be used in this documentation, for example the framework has a telegram interface, does it have a method for sending images? If so, use it instead of implementing your own method. They probably already built something for the problem you are trying to solve. If you cannot find it, then think about how to build it and ask if okay to continue with your plan.
3. **Check the current implementation state.**
Make sure that the existing layer works correctly before you add new capabilities.
4. **Confirm deviations.**
If a task requires a deviation from official best practices, ask the user for approval first.