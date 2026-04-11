Since our local interface is essentially a richer version of the shared API,  it is relatively straightforward to adapt our existing implementation to the standardized interface.

Our approach is to have the implementation class extend both our locally defined interface (from Homework 1) and the shared interface:

```python
from calendar_client_api import CalendarClient
from ospsd_calendar_api import CalendarClient as SharedCalendarClient

class GoogleCalendarClient(CalendarClient, SharedCalendarClient):
    ...
```

However, this introduces some challenges. In particular, there are method signature conflicts between the shared interface and our local interface, and Python does not support method overloading based on different parameter types or return types.

To address this, we refactor our locally defined interface by renaming the methods. And we implement the new methods by delegating the work to the existing methods.
