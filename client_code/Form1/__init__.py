from ._anvil_designer import Form1Template
from anvil import *
import anvil.server


class Form1(Form1Template):
  def __init__(self, **properties):
    self.init_components(**properties)
    self.load_data()

  def load_data(self):
    self.repeating_panel_1.items = anvil.server.call('get_person_leaderboard')

  def refresh_button_click(self, **event_args):
    self.load_data()