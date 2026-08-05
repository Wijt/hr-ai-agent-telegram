# Engineering Principles and Agent Rules

Read this document before you write code. It contains no implementation details.

## 1. Core Principles

### Keep It Simple

* Simple means consistent. Do not build two architectures for one problem.
* Obey the patterns of the framework.

### Add Complexity Step by Step

* Write the smallest end-to-end system that works first.
* Make sure that the current layer works before you add the next layer.
* Do not design for future needs at the start.

### Obey Official Best Practices

* Read the official documentation before you write code. Obey its examples.
* If you must deviate, give the user the reason and get approval first.

### Tools Return Data, Not Messages

* Write each tool so that it returns structured data, not a ready message.
* Let the chat agent decide how to show the result.

Reason: Formatted text locks the presentation. Then the agent cannot adapt the result to the request.

### Let the Agent Do the Work It Can Do

* Do not write a special function for a message that the agent can write.

Reason: A separate function causes a separate model call and a flow that is absent from the history of the agent.

### One Rule, One Place

* If two features need the same decision, write that rule one time.
* Apply this to prompts and to code. A tool docstring is part of the prompt.

---

## 2. System Design

### Context

* Do not send raw file content to the main model context.
* Send structured data between workflow steps.

### Match State Keys to State Lifetime

* Key shared state by the thing that owns it.
* If one unit of work spans concurrent tasks, make one state object and pass it by reference.

Reason: The next unit of work overwrites a key that lives longer than its state.

### Extract the Shared Shell

* If the same wrapper occurs around a call three times, extract it.

Reason: Copies become different over time, and the difference shows as an error in one copy only.

### Concurrency

* A block with no `await` runs atomically. Use this instead of a lock.
* Do not read shared state with a destructive operation in that block.
* Serialize the calls that write to the same session row.

Reason: If N tasks wait for one event, a destructive read gives the correct value to the first task only.

---

## 3. Prompt and Instruction Design

* Treat instructions as code. Keep named sections and refactor them.
* Do not correct behavior with one more sentence at the end.
* If an injected note gives the model a set of branches, add the branch for "no match".
* Do not let an injected note block the request of the user. Answer the request first.
* If a tool returns data, write in the instructions what the agent must not remove.

---

## 4. Pre-Action Checklist

1. Read Section 1 before you write or change code.
2. Search the official documentation for the pattern. The framework often contains the function that you plan to write.
3. Make sure that the existing layer works before you add a new capability.
4. If the behavior depends on the framework, read the installed source. Do not assume.
5. Report the findings and let the user select the items.
6. Argue against your own report before you start. What is absent? What is in the wrong order?
7. Complete one item and make sure that it works. Then start the next item.
8. A compile test proves nothing about behavior. The user does a live test before the merge.
9. Record the invariant and the error that caused it.
