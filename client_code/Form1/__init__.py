from ._anvil_designer import Form1Template
from anvil import *
import anvil.server


class Form1(Form1Template):
  def __init__(self, **properties):
    self.init_components(**properties)
    self.load_data()

  def load_data(self):
    rows = anvil.server.call("get_person_leaderboard")
    self.repeating_panel_1.items = rows

  def refresh_button_click(self, **event_args):
    self.refresh_button.enabled = False
    self.refresh_button.text = "Refreshing..."

    try:
      anvil.server.call("refresh_person_leaderboard")
      self.load_data()
      Notification("Leaderboard updated").show()
    except Exception as e:
      alert(f"Refresh failed: {e}")
    finally:
      self.refresh_button.enabled = True
      self.refresh_button.text = "Refresh"