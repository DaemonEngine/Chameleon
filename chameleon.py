#!/usr/bin/env python3
# Needs Python >= 3.3, PyQt4


# Copyright 2013 Unvanquished Development
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from PyQt4 import QtGui, QtCore
from PIL   import Image
from io    import BytesIO

import sys
import os
import pickle
import copy
import zipfile
import math


class Static():
	TITLE = "Chameleon"
	
	PREVIEW_WIDTH = 128
	PREVIEW_HEIGHT = 128
	
	TEXTURE_EXTENSIONS = ("tga", "png", "jpg", "jpeg", "webp", "crn") # no "."
	
	MAP_FILE_EXTENSION = ".map"
	RULE_FILE_EXTENSION = ".rules"
	
	if os.name == "nt":
		DEFAULT_BASEPATH = os.path.expandvars("%PROGRAMFILES%\\Unvanquished")
		DEFAULT_HOMEPATH = os.path.expandvars("%APPDATA%\\Roaming\\Daemon")
		SETTINGS_DIR = os.path.expandvars("%APPDATA%\\" + TITLE)
	else: # assume posix
		DEFAULT_BASEPATH = "/usr/share/unvanquished"
		DEFAULT_HOMEPATH = os.path.expanduser("~/.unvanquished")
		SETTINGS_DIR = os.path.expanduser("~/." + TITLE.lower())
	
	if not os.path.isdir(SETTINGS_DIR):
		os.mkdir(SETTINGS_DIR) # exceptions uncatched on purpose
	
	SHADER_CACHE_FILE = SETTINGS_DIR + os.sep + "shader_cache.dat"
	SESSION_FILE = SETTINGS_DIR + os.sep + "session.dat"
	
	@staticmethod
	def progressDialog():
		pd = QtGui.QProgressDialog("Loading available shaders ...", None, 0, 1)
		pd.show()
		return pd
	
	
class Session():
	def __init__(self, model):
		self.model = model
		
		self.lastmap = None
		self.lastmapdir = None
		self.lastrules = None
		self.lastrulesdir = None
		self.lastshadersets = None
		self.shaderpickergeom = None
		
	def saveSession(self, path):
		with open(path, "wb") as f:
			state = self.__dict__.copy()
			del state["model"]
			
			pickle.dump(state, f)
			
	def restoreSession(self, path):
		with open(path, "rb") as f:
			state = pickle.load(f)
			
			self.__dict__.update(state)
			
	def getLastMap(self):
		return self.lastmap
	
	def getLastMapDir(self):
		if self.lastmapdir != None:
			return self.lastmapdir
		
		homepath = self.model.shaders.getHomepath()
		
		if homepath != None:
			return homepath
		else:
			return Static.DEFAULT_HOMEPATH
	
	def getLastRules(self):
		return self.lastrules
	
	def getLastRulesDir(self):
		if self.lastrulesdir != None:
			return self.lastrulesdir
		else:
			return Static.SETTINGS_DIR
	
	def getLastShaderSets(self):
		return self.lastshadersets
	
	def getShaderPickerGeometry(self):
		return self.shaderpickergeom
	
	def setLastMap(self, path):
		if os.path.isfile(path):
			self.lastmap = path
		
		dir_ = path.rsplit(os.sep, 1)[0]
		if os.path.isdir(dir_):
			self.lastmapdir = dir_
			
	def setLastRules(self, path):
		if os.path.isfile(path):
			self.lastrules = path
		
		dir_ = path.rsplit(os.sep, 1)[0]
		if os.path.isdir(dir_):
			self.lastrulesdir = dir_
			
	def setLastShaderSets(self, names):
		self.lastshadersets = names
		
	def setShaderPickerGeometry(self, geom):
		self.shaderpickergeom = geom


# TODO: Allow setting of long floats in shader table
class ShaderTableModel(QtCore.QAbstractTableModel):
	def __init__(self, model):
		QtCore.QAbstractTableModel.__init__(self)
		
		self.model = model
		
		self.headers = \
		[
			"Count",
			"Old Shader",
			"Old Size",
			"Old Preview",
			"New Preview",
			"New Size",
			"New Shader",
			"H Scale",
			"V Scale",
			"Rotation"
		]
		
		self.columns = len(self.headers)
		
		self.h2c = dict() # header -> column
		for col in range(len(self.headers)):
			self.h2c[self.headers[col]] = col
			
	def reset(self):
		self.beginResetModel()
		self.endResetModel()
		
	def markChanged(self, row, newOnly):
		if newOnly:
			begin = 4
		else:
			begin = 0
			
		self.dataChanged.emit(self.index(row, begin), self.index(row, self.columns - 1))
	
	def rowCount(self, index = None):
		return self.model.map.distinctShaders()
	
	def columnCount(self, index = None):
		return self.columns
	
	def headerData(self, section, direction, role = QtCore.Qt.DisplayRole):
		if direction == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
			return self.headers[section]
		else:
			return QtCore.QAbstractTableModel.headerData(self, section, direction, role)
	
	def flags(self, index):
		if index.column() in (7, 8, 9):
			return QtCore.Qt.ItemFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable)
		else:
			return QtCore.Qt.ItemFlags(QtCore.Qt.ItemIsEnabled)
		
	def setData(self, index, value, role = QtCore.Qt.EditRole):
		if role != QtCore.Qt.EditRole:
			return False
		
		shader = self.model.map.indexToShader(index.row())
		
		if shader not in self.model.rules:
			return False
		
		row = index.row()
		col = index.column()
		
		if   col == 7:
			self.model.rules.setHScale(shader, value)
			self.dataChanged.emit(index, index)
		elif col == 8:
			self.model.rules.setVScale(shader, value)
			self.dataChanged.emit(index, index)
		elif col == 9:
			self.model.rules.setRotation(shader, value)
			self.markChanged(row, True)
		else:
			return False
		
		return True
	
	def data(self, index, role):
		row = index.row()
		col = index.column()

		if not index.isValid() \
		or row not in range(self.rowCount()) \
		or col not in range(self.columnCount()):
			return None
		
		shader = self.model.map.indexToShader(row)
		
		# preview images
		if col in (3, 4):
			if col == 3:
				preview = self.model.shaders.getPreview(shader)
			else: # col == 4
				if shader in self.model.rules:
					new_shader = self.model.rules.getNewShader(shader)
					hscale = self.model.rules.getHScale(shader)
					vscale = self.model.rules.getVScale(shader)
					rot = self.model.rules.getRotation(shader)
					preview = self.model.shaders.getPreview(new_shader, shader, hscale, vscale, rot)
				else:
					preview = self.model.shaders.getPreview()
			
			if   role == QtCore.Qt.DecorationRole:
				return preview
			elif role == QtCore.Qt.SizeHintRole:
				return QtCore.QSize(preview.width(), preview.height())
			else:
				return None
		
		if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
			if   col == 0:
				return str(self.model.map.appearance(shader))
			elif col == 1:
				return shader
			elif col == 2:
				return self.model.shaders.getResolution(shader)
			elif col == 5:
				if shader in self.model.rules:
					new_shader = self.model.rules.getNewShader(shader)
					return self.model.shaders.getResolution(new_shader)
			elif col == 6:
				if shader in self.model.rules:
					return self.model.rules.getNewShader(shader)
			elif col == 7:
				if shader in self.model.rules:
					return self.model.rules.getHScale(shader)
			elif col == 8:
				if shader in self.model.rules:
					return self.model.rules.getVScale(shader)
			elif col == 9:
				if shader in self.model.rules:
					return self.model.rules.getRotation(shader)
				
		return None


class ShaderSourcesWizzard(QtGui.QWizard):
	def __init__(self, model):
		QtGui.QWizard.__init__(self)
		
		self.model = model
		
		old_basepath = self.model.shaders.getBasepath()
		old_homepath = self.model.shaders.getHomepath()
		
		if old_basepath == None:
			basepath = Static.DEFAULT_BASEPATH
		else:
			basepath = old_basepath
		
		if old_homepath == None:
			homepath = Static.DEFAULT_HOMEPATH
		else:
			homepath = old_homepath
		
		self.basepathField = QtGui.QLineEdit(basepath)
		self.homepathField = QtGui.QLineEdit(homepath)
		
		self.setWindowTitle("Chameleon - Settings")
		self.addPage(self.ShaderSourcesWizzardPage1(self))
	
	def accept(self):
		self.model.loadShaders(Static.progressDialog(), self.basepathField.text(), self.homepathField.text())
		
		self.close()

	# TODO: add wizzard pages for 1) select mods 2) select sources
	
	class ShaderSourcesWizzardPage1(QtGui.QWizardPage):
		def __init__(self, parent):
			QtGui.QWizardPage.__init__(self, parent)
			
			self.parent = parent
			
			layout = QtGui.QFormLayout()
			layout.addWidget(QtGui.QLabel("Game settings"))
			layout.addRow("Basepath", parent.basepathField)
			layout.addRow("Homepath", parent.homepathField)
			self.setLayout(layout)
			
		def validatePage(self):
			# TODO: validatePage doesn't work
			
			basepath = os.path.expandvars(self.parent.basepathField.text())
			homepath = os.path.expandvars(self.parent.homepathField.text())
			
			if os.path.isdir(basepath) and os.path.isdir(homepath):
				return True
			else:
				return False


class ShaderPickerListModel(QtCore.QAbstractListModel):
	def __init__(self, model, shaders):
		QtCore.QAbstractListModel.__init__(self)
		self.model = model
		self.shaders = shaders
		
	def rowCount(self, index = None):
		return len(self.shaders)
		
	def data(self, index, role):
		shader = self.shaders[index.row()]
		
		if role == QtCore.Qt.DecorationRole:
			return self.model.shaders.getPreview(shader)
		elif role == QtCore.Qt.DisplayRole:
			return shader.split("/", 1)[-1]


class ShaderPicker(QtGui.QDialog):
	def __init__(self, view, model, old_shader):
		QtGui.QDialog.__init__(self)
		self.view = view
		self.model = model
		self.old_shader = old_shader
		
		self.clear = False
		self.selected_shaders = list()
		
		if old_shader in self.model.rules:
			self.new_shader = self.model.rules.getNewShader(old_shader)
		else:
			self.new_shader = None
		
		self.accepted = False
		
		self.setname2item = dict()
		
		# configure window
		self.setWindowTitle("Pick a replacement for " + self.old_shader)
		
		# create widgets
		self.old_data_label = QtGui.QLabel(self.old_shader + "\n" + self.model.shaders.getResolution(self.old_shader), self)
		self.old_data_label.setAlignment(QtCore.Qt.AlignRight)
		self.old_data_label.setMinimumWidth(256)
		self.old_data_label.setMaximumWidth(256)
		
		self.old_preview_label = QtGui.QLabel(self)
		self.old_preview_label.setMinimumSize(Static.PREVIEW_WIDTH, Static.PREVIEW_HEIGHT)
		self.old_preview_label.setAlignment(QtCore.Qt.AlignRight)
		self.old_preview_label.setPixmap(self.model.shaders.getPreview(old_shader))
		
		self.new_preview_label = QtGui.QLabel(self)
		self.new_preview_label.setMinimumSize(Static.PREVIEW_WIDTH, Static.PREVIEW_HEIGHT)
		self.new_preview_label.setAlignment(QtCore.Qt.AlignLeft)
		self.new_preview_label.setPixmap(self.model.shaders.getPreview(self.new_shader))
		
		if self.new_shader != None:
			self.new_data_label = QtGui.QLabel(self.new_shader + "\n" + self.model.shaders.getResolution(self.new_shader), self)
		else:
			self.new_data_label = QtGui.QLabel(self)
		self.new_data_label.setAlignment(QtCore.Qt.AlignLeft)
		self.new_data_label.setMinimumWidth(256)
		self.new_data_label.setMaximumWidth(256)
		
		self.set_list = QtGui.QListWidget(self)
		self.set_list.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
		self.set_list.setMinimumWidth(180)
		self.set_list.setMaximumWidth(180)
		for setname in self.model.shaders.getSets():
			item = QtGui.QListWidgetItem(setname)
			self.set_list.addItem(item)
			self.setname2item[setname] = item
		
		self.shader_list = QtGui.QListView(self)
		self.shader_list.setViewMode(QtGui.QListView.IconMode)
				
		self.replace_button = QtGui.QPushButton("Replace", self)
		self.cancel_button = QtGui.QPushButton("Cancel", self)
		self.clear_button = QtGui.QPushButton("Clear", self)
		
		# assemble layout
		toplayout = QtGui.QHBoxLayout()
		toplayout.addWidget(self.old_data_label)
		toplayout.addWidget(self.old_preview_label)
		toplayout.addWidget(self.new_preview_label)
		toplayout.addWidget(self.new_data_label)
		
		centerlayout = QtGui.QHBoxLayout()
		centerlayout.addWidget(self.set_list)
		centerlayout.addWidget(self.shader_list)
		
		bottomlayout = QtGui.QHBoxLayout()
		bottomlayout.addWidget(self.replace_button)
		bottomlayout.addWidget(self.cancel_button)
		bottomlayout.addWidget(self.clear_button)
		
		rootlayout = QtGui.QVBoxLayout()
		rootlayout.addLayout(toplayout)
		rootlayout.addLayout(centerlayout)
		rootlayout.addLayout(bottomlayout)
		
		self.setLayout(rootlayout)
		
		# connect signals
		QtCore.QObject.connect(self.set_list, QtCore.SIGNAL("itemSelectionChanged()"), self.__handleSelectedSets)
		QtCore.QObject.connect(self.shader_list, QtCore.SIGNAL("clicked(QModelIndex)"), self.__handleClickedShader)
		QtCore.QObject.connect(self.replace_button, QtCore.SIGNAL("clicked()"), self.__handleReplace)
		QtCore.QObject.connect(self.cancel_button, QtCore.SIGNAL("clicked()"), self.__handleCancel)
		QtCore.QObject.connect(self.clear_button, QtCore.SIGNAL("clicked()"), self.__handleClear)
		
		# restore selected sets
		lastsets = self.view.session.getLastShaderSets()
		if lastsets != None:
			selection = QtGui.QItemSelection()
			
			for setname in lastsets:
				if setname in self.setname2item:
					index = self.set_list.indexFromItem(self.setname2item[setname])
					selection.select(index, index)
					
			self.set_list.selectionModel().select(selection, QtGui.QItemSelectionModel.Select)
			
		# restore geometry
		geom = self.view.session.getShaderPickerGeometry()
		if geom != None:
			self.restoreGeometry(geom)
			
	def getNewShader(self):
		if self.accepted:
			return self.new_shader
		else:
			return None
	
	def getClear(self):
		return self.clear
	
	def resizeEvent(self, event):
		self.shader_list.reset()
	
	def __handleSelectedSets(self):
		setnames = [setname.text() for setname in self.set_list.selectedItems()]
		setnames.sort()
		
		self.view.session.setLastShaderSets(setnames)
		
		self.selected_shaders.clear()
		
		for setname in setnames:
			for shader in self.model.shaders.getShadersForSet(setname):
				self.selected_shaders.append(shader)
		
		self.__showShaders(self.selected_shaders)
	
	def __handleClickedShader(self, index):
		try:
			shader = self.selected_shaders[index.row()]
		except IndexError:
			return
		
		self.new_shader = shader
		
		self.new_data_label.setText(self.new_shader + "\n" + self.model.shaders.getResolution(shader))
		self.new_preview_label.setPixmap(self.model.shaders.getPreview(shader))
	
	def __showShaders(self, shaders):
		self.shader_list.setModel(ShaderPickerListModel(self.model, shaders))
		
	def __handleReplace(self):
		self.accepted = True
		
		self.close()
	
	def __handleCancel(self):
		self.close()
		
	def __handleClear(self):
		self.clear = True
		
		self.close()
		
	def closeEvent(self, event):
		self.close()
		
	def close(self):
		self.view.session.setShaderPickerGeometry(self.saveGeometry())
		
		QtGui.QDialog.close(self)


class View(QtGui.QMainWindow):
	def __init__(self, model):
		QtGui.QWidget.__init__(self)
		self.model = model
		self.session = Session(model)
		
		# configure window
		self.setWindowTitle(Static.TITLE)
		
		# create widgets
		self.menuMap = QtGui.QMenu("Map", self)
		self.actionOpenMap = self.menuMap.addAction("Open map", self.__handleOpenMap, "Ctrl+O")
		self.actionSaveMap = self.menuMap.addAction("Save map", self.__handleSaveMap, "Ctrl+S")
		self.actionSaveMap.setEnabled(False)
				
		self.menuRules = QtGui.QMenu("Rules", self)
		self.actionOpenRules = self.menuRules.addAction("Import rules", self.__handleOpenRules, "Ctrl+I")
		self.actionSaveRules = self.menuRules.addAction("Export rules", self.__handleSaveRules, "Ctrl+E")
		self.actionSaveRules.setEnabled(False)
		self.actionClearRules = self.menuRules.addAction("Clear rules", self.__handleClearRules)
		self.actionClearRules.setEnabled(False)
		
		self.menuShaders = QtGui.QMenu("Shaders", self)
		self.actionReloadShaders = self.menuShaders.addAction("Reload shaders", self.__handleReloadShaders, "Ctrl+R")
		self.actionSettings = self.menuShaders.addAction("Set shader sources", self.__handleSettings)
		
		self.statusLabel = QtGui.QLabel("", self)
		
		self.tableView = QtGui.QTableView()
		self.tableModel = ShaderTableModel(self.model)
		self.tableView.setModel(self.tableModel)
		
		# assemble layout
		menubar = QtGui.QMenuBar()
		menubar.addMenu(self.menuMap)
		menubar.addMenu(self.menuRules)
		menubar.addMenu(self.menuShaders)
		
		bottomlayout = QtGui.QHBoxLayout()
		bottomlayout.addWidget(self.statusLabel)
		
		rootlayout = QtGui.QVBoxLayout()
		rootlayout.addWidget(self.tableView)
		rootlayout.addLayout(bottomlayout)
		
		centerWidget = QtGui.QWidget()
		centerWidget.setLayout(rootlayout)
		
		self.setMenuBar(menubar)
		self.setCentralWidget(centerWidget)
		
		# connect signals
		QtCore.QObject.connect(self.tableView, QtCore.SIGNAL("clicked(QModelIndex)"), self.__handleTableClicked)
		
	def setStatus(self, status):
		"Called by Model.* to display stuff in the status bar."
		self.statusLabel.setText(status)
		
	def askSettings(self):
		"Called by __main__ to show configuration dialog."
		sw = ShaderSourcesWizzard(self.model)
		sw.exec_()
		
		self.__updateTable()
		
	def restoreSession(self):
		"Tries to read session data from filesystem."
		try:
			self.session.restoreSession(Static.SESSION_FILE)
		except FileNotFoundError:
			return False
		except BaseException as e:
			print("Failed to read session file " + Static.SESSION_FILE + ": " + str(e), file = sys.stderr)
			return False
		else:
			return True
		
	def closeEvent(self, event):
		try:
			self.session.saveSession(Static.SESSION_FILE)
		except BaseException as e:
			print("Failed to save session file " + Static.SESSION_FILE + ": " + str(e), file = sys.stderr)
		
		QtGui.QWidget.closeEvent(self, event)
		
	def keyPressEvent(self, event):
		if event.modifiers() & QtCore.Qt.ControlModifier:
			if event.key() == QtCore.Qt.Key_O:
				self.__handleOpenMap()
			elif event.key() == QtCore.Qt.Key_S:
				self.__handleSaveMap()
	
	def __updateRulesButton(self):
		if self.model.rules.empty():
			self.actionSaveRules.setEnabled(False)
			self.actionClearRules.setEnabled(False)
		else:
			self.actionSaveRules.setEnabled(True)
			self.actionClearRules.setEnabled(True)
	
	def __updateTable(self, rowOrShader = None, newOnly = True):
		if rowOrShader == None:
			self.tableModel.reset()
			self.tableView.resizeRowsToContents()
		else:
			if type(rowOrShader) == str:
				row = self.model.map.shaderToIndex(rowOrShader)
				
				if row == None:
					return
			else:
				row = rowOrShader
			
			self.tableModel.markChanged(row, newOnly)
			
		self.tableView.resizeColumnsToContents()
	
	def __handleTableClicked(self, index):
		if index.column() == 4: # new old_shader preview
			old_shader = self.model.map.indexToShader(index.row())
			
			picker = ShaderPicker(self, self.model, old_shader)
			picker.exec_()
			new_shader = picker.getNewShader()
			clear = picker.getClear()
			
			if clear:
				self.model.rules.delRule(old_shader)
			elif new_shader != None:
				self.model.rules.addRule(old_shader, new_shader)
			else:
				return
			
			self.__updateTable(old_shader)
			self.__updateRulesButton()			
			
	def __handleOpenMap(self):
		path = QtGui.QFileDialog.getOpenFileName(
			self,
			"Choose a map",
			self.session.getLastMapDir(),
			"*" + Static.MAP_FILE_EXTENSION
		)
		if path != "":
			self.model.openMap(path)
			
			self.session.setLastMap(path)
			
			self.setWindowTitle(Static.TITLE + " - " + os.path.basename(path))
			self.actionSaveMap.setEnabled(True)
			self.__updateTable()
		
	def __handleSaveMap(self):
		path = QtGui.QFileDialog.getSaveFileName(
			self, "Choose a destination",
			self.session.getLastMapDir(),
			"*" + Static.MAP_FILE_EXTENSION
		)
		if path != "":
			if not path.endswith(Static.MAP_FILE_EXTENSION):
				path += Static.MAP_FILE_EXTENSION
			self.model.saveMap(path)
	
	def __handleOpenRules(self):
		path = QtGui.QFileDialog.getOpenFileName(
			self,
			"Choose a rules file",
			self.session.getLastRulesDir(),
			"*" + Static.RULE_FILE_EXTENSION)
		if path != "":
			self.model.openRules(path)
			
			self.session.setLastRules(path)

		self.__updateRulesButton()
		self.__updateTable()

	def __handleClearRules(self):
		self.model.rules.clear()

		self.__updateRulesButton()
		self.__updateTable()
		self.setStatus("Rules cleared.")
	
	def __handleSaveRules(self):
		path = QtGui.QFileDialog.getSaveFileName(
			self,
			"Choose a destination",
			self.session.getLastRulesDir(),
			"*" + Static.RULE_FILE_EXTENSION
		)
		if path != "":
			if not path.endswith(Static.RULE_FILE_EXTENSION):
				path += Static.RULE_FILE_EXTENSION
			self.model.saveRules(path)
	
	def __handleReloadShaders(self):
		self.model.reloadShaders(Static.progressDialog())
		
		self.__updateTable()

	def __handleSettings(self):
		self.askSettings()


class Shaders():
	def __init__(self):
		self.basepath = None
		self.homepath = None
		self.shader_sources = list() # dirs/pk3s inside self.basepath/self.homepath
		self.shaders = dict() # shader name -> property -> value
		
		painter = QtGui.QPainter()
		
		# build NO PREVIEW image
		self.pixmap_not_found = QtGui.QPixmap(128, 128)
		self.pixmap_not_found.fill(QtCore.Qt.black)
		painter.begin(self.pixmap_not_found)
		painter.setPen(QtCore.Qt.red)
		painter.drawText(QtCore.QPointF(24, 67), "NOT FOUND")
		painter.end()
		
		# build UNSUPPORTED image
		self.pixmap_unsupported = QtGui.QPixmap(128, 128)
		self.pixmap_unsupported.fill(QtCore.Qt.black)
		painter.begin(self.pixmap_unsupported)
		painter.setPen(QtCore.Qt.yellow)
		painter.drawText(QtCore.QPointF(13, 67), "UNSUPPORTED")
		painter.end()
		
		# build REPLACE image
		self.pixmap_replace = QtGui.QPixmap(128, 128)
		self.pixmap_replace.fill(QtCore.Qt.black)
		painter.begin(self.pixmap_replace)
		painter.setPen(QtCore.Qt.white)
		painter.drawText(QtCore.QPointF(32, 67), "REPLACE")
		painter.end()
		
	def __contains__(self, shader):
		return shader in self.shaders
	
	def __len__(self):
		return len(self.shaders)
			
	def emtpy(self):
		return len(self) == 0
	
	def writeCache(self, path):
		with open(path, "wb") as f:
			shaders_copy = copy.deepcopy(self.shaders)
			
			# convert QPixmap to QByteArray
			for shader in self.shaders.keys():
				if not self.shaders[shader]["is_shader"]:
					preview = self.shaders[shader]["preview"]
					preview_bytes = QtCore.QByteArray()
					preview_buffer = QtCore.QBuffer(preview_bytes)
					preview_buffer.open(QtCore.QIODevice.WriteOnly)
					preview.save(preview_buffer, "JPG", 100)
					preview_buffer.close()
					shaders_copy[shader]["preview"] = preview_bytes
				
			state = (self.basepath, self.homepath, self.shader_sources, shaders_copy)
			
			pickle.dump(state, f)
	
	def readCache(self, path):
		with open(path, "rb") as f:
			state = pickle.load(f)
			
			(self.basepath, self.homepath, self.shader_sources, self.shaders) = state
			
			# convert QByteArray back to QPixmap
			for shader in self.shaders.keys():
				if not self.shaders[shader]["is_shader"]:
					preview_bytes = self.shaders[shader]["preview"]
					preview = QtGui.QPixmap()
					preview.loadFromData(preview_bytes)
					self.shaders[shader]["preview"] = preview
				
	def getPath(self, shader):
		if shader in self.shaders and not self.shaders[shader]["is_shader"]:
			return self.shaders[shader]["path"]
		else:
			return ""
	
	def getPreviewScale(self, shader):
		if shader in self.shaders:
			if self.shaders[shader]["is_shader"]:
				preview_source = self.shaders[shader]["preview_source"]
				if preview_source in self.shaders \
				and not self.shaders[preview_source]["is_shader"]: # prevent recursion
					return self.getPreviewScale(preview_source)
				else:
					return 1.0
			else:
				return self.shaders[shader]["preview_scale"]
		else:
			return 1.0
	
	def getPreview(self, shader = None, old_shader = None, hscale = None, vscale = None, rot = None):
		if shader == None:
			return self.pixmap_replace
		elif shader in self.shaders:
			if self.shaders[shader]["is_shader"]:
				preview_source = self.shaders[shader]["preview_source"]
				if preview_source in self.shaders \
				and not self.shaders[preview_source]["is_shader"]: # prevent recursion
					return self.getPreview(preview_source, old_shader, hscale, vscale, rot)
				else:
					return self.pixmap_not_found
			else:
				if self.shaders[shader]["width"] == self.shaders[shader]["height"] == 0:
					return self.pixmap_unsupported
				else:
					if old_shader in self.shaders and hscale != None and vscale != None and rot != None:
						scale = self.getPreviewScale(shader) / self.getPreviewScale(old_shader)
						hscale /= scale
						vscale /= scale
						trans_scale = QtGui.QTransform().scale(hscale, vscale)
						trans_rot = QtGui.QTransform().rotate(rot)
						return self.shaders[shader]["preview"].transformed(trans_scale).transformed(trans_rot)
					else:
						return self.shaders[shader]["preview"]
		else:
			return self.pixmap_not_found
	
	def getWidth(self, shader):
		if shader in self.shaders:
			if self.shaders[shader]["is_shader"]:
				preview_source = self.shaders[shader]["preview_source"]
				if preview_source in self.shaders \
				and not self.shaders[preview_source]["is_shader"]: # prevent recursion
					return self.getWidth(preview_source)
				else:
					return 0
			else:
				return self.shaders[shader]["width"]
		else:
			return 0
		
	def getHeight(self, shader):
		if shader in self.shaders:
			if self.shaders[shader]["is_shader"]:
				preview_source = self.shaders[shader]["preview_source"]
				if preview_source in self.shaders \
				and not self.shaders[preview_source]["is_shader"]: # prevent recursion
					return self.getHeight(preview_source)
				else:
					return 0
			else:
				return self.shaders[shader]["height"]
		else:
			return 0

	def sizeKnown(self, shader):
		return self.getWidth(shader) > 0 and self.getHeight(shader) > 0
		
	def getResolution(self, shader):
		return str(self.getWidth(shader)) + " x " + str(self.getHeight(shader))
		
	def loadShaders(self, pd, basepath, homepath, reload = False):
		"Updates self.basepath and self.homepath and loads shader data from disk if the pathes have changed."
		if self.basepath != basepath or self.homepath != homepath or reload:
			necessary = True
		else:
			necessary = False
		
		self.basepath = basepath
		self.homepath = homepath
		
		if necessary:
			self.__updateShaderSources(pd)
			self.__updateShaderData(pd)
			
		return necessary
		
	def reloadShaders(self, pd):
		"Reloads shader data from disk."
		self.loadShaders(pd, self.basepath, self.homepath, True)
			
	def getBasepath(self):
		return self.basepath
	
	def getHomepath(self):
		return self.homepath		
	
	# TODO: cache getSets answer?
	def getSets(self):
		sets = set()
		
		for shader in self.shaders.keys():
			sets.add(shader.split("/", 1)[0])
	
		sorted_sets = list(sets)
		sorted_sets.sort()
		
		return sorted_sets
		
	# TODO: cache getShadersForSets answer?
	def getShadersForSet(self, setname):
		shaders = [shader for shader in self.shaders.keys() if shader.startswith(setname +  "/")]
		shaders.sort()
		
		return shaders
		
	def __updateShaderSources(self, pd):
		"""Writes pathes of mod directories and their pak files/dirs inside self.basepath
		and self.homepath into self.shader_sources."""
		self.shader_sources.clear()
		
		for path in (self.basepath, self.homepath):
			if path != None:
				path = os.path.expanduser(path).rstrip(os.sep)
				
				if not os.path.isdir(path):
					continue
				
				mods = list()
				for node in os.listdir(path):
					if os.path.isdir(path + os.sep + node):
						mods.append(node)
				
				for mod in mods:
					mod_path = path + os.sep + mod
					self.shader_sources.append(mod_path)
					
					for node in os.listdir(mod_path):
						for pak_type in ["pk3", "dpk"]:
							if node.endswith(os.extsep + pak_type) or node.endswith(os.extsep + pak_type + "dir"):
								self.shader_sources.append(mod_path + os.sep + node)
							
		pd.setMaximum(len(self.shader_sources))

	def __PIL2QPixmap(self, pilImage):
		(r,g,b,a) = pilImage.convert("RGBA").split()
		rawImage  = Image.merge("RGBA", (b,g,r,a)).tobytes("raw", "RGBA")
		qImage    = QtGui.QImage(rawImage, pilImage.size[0], pilImage.size[1], QtGui.QImage.Format_ARGB32)
		qPixmap   = QtGui.QPixmap.fromImage(qImage)
		return qPixmap

	def __createPixmap(self, target):
		if ( type(target) == bytes ):
			target = BytesIO(target)

		try:
			pilImage = Image.open(target)
		except OSError:
			# this usually means unsupported image format
			return QtGui.QPixmap()

		return self.__PIL2QPixmap(pilImage)

	def __updateShaderData(self, pd):
		"Writes database of shaders inside self.shader_sources into self.shaders."
		self.shaders.clear()
		
		progress = 0
		for path in self.shader_sources:
			if os.path.isdir(path):
				self.__getShaderDataFromDir(path)
			elif os.path.isfile(path):
				self.__getShaderDataFromPk3(path)
		
			progress += 1
			pd.setValue(progress)
				
	def __getShaderDataFromDir(self, path):
		ls = os.listdir(path)
		
		if "scripts" in ls:
			for shader in [
				path + os.sep + "scripts" + os.sep + node
				for node in os.listdir(path + os.sep + "scripts")
				if node.endswith(".shader")
			]:
				with open(shader) as f:
					self.__parseShaderFileContent(shader, f.read())
		
		if "textures" in ls:
			for directory in [
				path + os.sep + "textures" + os.sep + node
				for node in os.listdir(path + os.sep + "textures")
				if os.path.isdir(path + os.sep + "textures" + os.sep + node)
			]:
				self.__parseTextureDir(directory)
		
	def __getShaderDataFromPk3(self, path):
		try:
			pk3 = zipfile.ZipFile(path)
		except zipfile.BadZipFile:
			return
		
		for pk3_path in pk3.namelist():
			combined_path = path + ":" + pk3_path
			
			if  pk3_path.startswith("textures/") \
			and pk3_path.rsplit(".", 1)[-1].lower() in Static.TEXTURE_EXTENSIONS:
				name = pk3_path[9:].rsplit(".", 1)[0]
				
				#preview = QtGui.QPixmap()
				#preview.loadFromData(pk3.read(pk3_path))
				preview = self.__createPixmap(pk3.read(pk3_path))
				
				width = preview.width()
				height = preview.height()
				
				if not preview.isNull():
					preview = preview.scaled(128, 128, QtCore.Qt.KeepAspectRatio)
					
				self.__addTexture(name, combined_path, preview, width, height)
				
			elif pk3_path.startswith("scripts/") and pk3_path.endswith(".shader"):
				self.__parseShaderFileContent(combined_path, pk3.read(pk3_path))
	
	def __parseShaderFileContent(self, path, content):
		if type(content) == bytes:
			try:
				content = content.decode("ascii")
			except UnicodeDecodeError as e:
				print("Failed to convert a shader file " + path + " to ascii: " + str(e), file = sys.stderr)
				return
			
		shader = None
		for line in content.splitlines():
			if line.isspace() or line.strip().startswith("//"):
				continue
			
			line = line.split("//", 1)[0]
			
			if line.startswith("textures/"):
				if shader != None:
					self.__parseShaderText(path, shader)
				shader = line
			elif shader != None:
				shader += ("\n" + line)
		
		# parse last shader
		if shader != None:
			self.__parseShaderText(path, shader)
	
	def __parseShaderText(self, path, text):
		lines = text.splitlines()
		
		name = lines.pop(0).split("/", 1)[-1]
		preview_source = None
		
		qer_editorimage = None
		diffusemap = None
		random_map = None # if no qer_editorimage/diffusemap is set, use the last map we've seen
		
		for line in lines:
			line = line.strip()
			line_lower = line.lower()
			
			try:
				if line_lower.startswith("qer_editorimage"):
					qer_editorimage = line.split(None, 1)[-1]
				elif line_lower.startswith("diffusemap"):
					diffusemap = line.split(None, 1)[-1]
				elif line_lower.startswith("map") and "textures/" in line:
					random_map = line.split(None, 1)[-1]
			except IndexError:
				return
			
			if qer_editorimage != None:
				preview_source = qer_editorimage
			elif diffusemap != None:
				preview_source = diffusemap
			elif random_map != None:
				preview_source = random_map
		
		if preview_source != None:
			preview_source = preview_source.split("/", 1)[-1].rsplit(".", 1)[0]
			self.__addShader(name, path, preview_source, text)
	
	def __parseTextureDir(self, directory):
		for node in [
			node
			for node in os.listdir(directory)
			if os.path.isfile(directory + os.sep + node)
			and node.rsplit(".", 1)[-1].lower() in Static.TEXTURE_EXTENSIONS
		]:
			name = os.path.basename(directory) + "/" + node.rsplit(".", 1)[0]
			path = directory + os.sep + node
			
			#preview = QtGui.QPixmap()
			#preview.load(path)
			preview = self.__createPixmap(path)
			
			width = preview.width()
			height = preview.height()
			
			if not preview.isNull():
				preview = preview.scaled(128, 128, QtCore.Qt.KeepAspectRatio)
			
			self.__addTexture(name, path, preview, width, height)

	def __addTexture(self, name, path, preview, width, height):
		"Adds a single loose texture to the database."
		self.shaders[name] = dict()
		self.shaders[name]["is_shader"] = False
		self.shaders[name]["path"] = path
		self.shaders[name]["preview"] = preview
		self.shaders[name]["preview_source"] = None
		if preview.width() > 0 and width > 0:
			self.shaders[name]["preview_scale"] = preview.width() / width
		else:
			self.shaders[name]["preview_scale"] = 1.0
		self.shaders[name]["width"] = width
		self.shaders[name]["height"] = height
		self.shaders[name]["shader"] = None
	
	def __addShader(self, name, path, preview_source, text):
		self.shaders[name] = dict()
		self.shaders[name]["is_shader"] = True
		self.shaders[name]["path"] = path
		self.shaders[name]["preview"] = None
		self.shaders[name]["preview_source"] = preview_source
		self.shaders[name]["preview_scale"] = None
		self.shaders[name]["width"] = None
		self.shaders[name]["height"] = None
		self.shaders[name]["shader"] = text
		
		
class Map():
	def __init__(self, model):
		self.model = model
		
		self.content = None
		self.shader_counter = dict() # shader -> count
		self.index2shader = dict() # table row -> shader
		self.shader2index = dict() # shader -> table row
		
	def __contains__(self, shader):
		return shader in self.shader_counter
	
	def __len__(self):
		return len(self.shader_counter)
		
	def distinctShaders(self):
		return len(self.shader_counter)
	
	def appearance(self, shader):
		if shader in self.shader_counter:
			return self.shader_counter[shader]
		else:
			return 0
	
	def shaderToIndex(self, shader):
		if shader in self.shader2index:
			return self.shader2index[shader]
		else:
			return None
	
	def indexToShader(self, index):
		if index in self.index2shader:
			return self.index2shader[index]
		else:
			return None
		
	def parse(self, content):
		self.content = content
		self.shader_counter.clear()
		
		for line in content.splitlines():
			words=line.split()

			if len(words) == 24:
				shader = words[15]
			elif len(words) == 1 and "/" in words[0]:
				shader = words[0]
			else:
				shader = None

			if shader:
				self.shader_counter.setdefault(shader, 0)
				self.shader_counter[shader] += 1
		
		self.__generateShaderOrder()
				
	def __generateShaderOrder(self):
		self.index2shader.clear()
		self.shader2index.clear()
		
		tmp = [(count, name) for (name, count) in self.shader_counter.items()]
		tmp.sort(reverse = True)
		position = 0
		for (count, name) in tmp:
			self.index2shader[position] = name
			self.shader2index[name] = position
			position += 1
	
	# unused but might come in handy at a later moment
#	def __faceRotation(self, p1_x, p1_y, p1_z, p2_x, p2_y, p2_z, p3_x, p3_y, p3_z, debug = False):
#		"""Takes the vertices of a triangle describing a brush face in 3D space as an argument and
#		calculates the rotation of the face around the texture projection axis."""
#		
#		# V contains the vertices of the given triangle
#		V = {
#			0: {"x": p1_x, "y": p1_y, "z": p1_z},
#			1: {"x": p2_x, "y": p2_y, "z": p2_z},
#			2: {"x": p3_x, "y": p3_y, "z": p3_z}
#		}
#		
#		# r is the vertice at the right angle of V
#		r = max(
#				((p2_x - p3_x)**2 + (p2_y - p3_y)**2 + (p2_z - p3_z)**2, 0),
#				((p1_x - p3_x)**2 + (p1_y - p3_y)**2 + (p1_z - p3_z)**2, 1),
#				((p1_x - p2_x)**2 + (p1_y - p2_y)**2 + (p1_z - p2_z)**2, 2)
#		)[1]
#		
#		# u and v are vectors that span a plain orthogonal to V
#		u = dict()
#		v = dict()
#		for axis in ("x", "y", "z"):
#			u[axis] = V[r][axis] - V[(r - 1) % 3][axis]
#			v[axis] = V[r][axis] - V[(r + 1) % 3][axis]
#		
#		# n = u x v is the normal vector of the plain spanned by u and v
#		n = dict()
#		n["x"] = u["y"] * v["z"] - u["z"] * v["y"]
#		n["y"] = u["z"] * v["x"] - u["x"] * v["z"]
#		n["z"] = u["x"] * v["y"] - u["y"] * v["x"]
#		
#		# the projection axis is the axis most "similar" to n
#		projection_axis = max(
#			(n["x"], "x"),
#			(n["y"], "y"),
#			(n["z"], "z")
#		)[1]
#		
#		if   projection_axis == "x":
#			angle = math.atan2(u["y"], u["z"])
#		elif projection_axis == "y":
#			angle = math.atan2(u["x"], u["z"])
#		else:
#			angle = math.atan2(u["x"], u["y"])
#		
#		if debug:
#			print("Vertice 0: "+str(p1_x)+" "+str(p1_y)+" "+str(p1_z))
#			print("Vertice 1: "+str(p2_x)+" "+str(p2_y)+" "+str(p2_z))
#			print("Vertice 2: "+str(p3_x)+" "+str(p3_y)+" "+str(p3_z))
#			print("Right angle vertice: "+str(r))
#			print("Span vector u: "+str(u["x"])+" "+str(u["y"])+" "+str(u["z"]))	
#			print("Span vector v: "+str(v["x"])+" "+str(v["y"])+" "+str(v["z"]))
#			print("Normal vector n: "+str(n["x"])+" "+str(n["y"])+" "+str(n["z"]))
#			print("Projection axis: "+projection_axis)
#			print("Angle: "+str(math.degrees(angle)))
#		
#		return angle
		
	def build(self, rules):
		new_content = ""
		replaced_faces = 0
		replaced_patches = 0
		
		inside_patch = False
#		patch_old = patch_new = patch_rule_rot = patch_rule_rot_rad = patch_rule_hscale = patch_rule_vscale = None

		for line in self.content.splitlines():
			words = line.split()
			
			# brush
			if len(words) == 24 and words[15] in rules:
#				(p1_x, p1_y, p1_z) = [float(i) for i in words[1:4]]
#				(p2_x, p2_y, p2_z) = [float(i) for i in words[6:9]]
#				(p3_x, p3_y, p3_z) = [float(i) for i in words[11:14]]
				
				old = words[15]
				old_hshift = float(words[16])
				old_vshift = float(words[17])
				old_rot = float(words[18])
				old_hscale = float(words[19])
				old_vscale = float(words[20])
				
				new = rules.getNewShader(old)
				rule_hscale = rules.getHScale(old)
				rule_vscale = rules.getVScale(old)
				rule_rot = rules.getRotation(old)
				rule_rot_rad = math.radians(rule_rot)
				
				new_rot = (old_rot + rule_rot) % 360.0

				new_hscale = (math.cos(rule_rot_rad)**2 * old_hscale  \
				           +  math.sin(rule_rot_rad)**2 * old_vscale) \
				           *  rule_hscale

				new_vscale = (math.cos(rule_rot_rad)**2 * old_vscale  \
				           +  math.sin(rule_rot_rad)**2 * old_hscale) \
				           *  rule_vscale

				if old in self.model.shaders and new in self.model.shaders \
				and self.model.shaders.sizeKnown(old) and self.model.shaders.sizeKnown(new):
					old_hshift_ratio = old_hshift / self.model.shaders.getWidth(old)
					old_vshift_ratio = old_vshift / self.model.shaders.getHeight(old)
					
					old_hshift_ratio -= int(old_hshift_ratio)
					old_vshift_ratio -= int(old_vshift_ratio)
					
					new_hshift_ratio = math.cos(rule_rot_rad)**2 * old_hshift_ratio \
					                 + math.sin(rule_rot_rad)**2 * old_vshift_ratio
					new_vshift_ratio = math.cos(rule_rot_rad)**2 * old_vshift_ratio \
					                 + math.sin(rule_rot_rad)**2 * old_hshift_ratio
					
					new_hshift_ratio -= int(new_hshift_ratio)
					new_vshift_ratio -= int(new_vshift_ratio)
					
					new_hshift = new_hshift_ratio * self.model.shaders.getWidth(new)
					new_vshift = new_vshift_ratio * self.model.shaders.getHeight(new)
				else:
					new_hshift = old_hshift / rule_hscale
					new_vshift = old_vshift / rule_vscale
				
				new_line = " ".join(words[0:15]) \
				         + " " + new \
				         + " " + str(new_hshift) \
				         + " " + str(new_vshift) \
				         + " " + str(new_rot) \
				         + " " + str(new_hscale) \
				         + " " + str(new_vscale) \
				         + " " + " ".join(words[21:24])
				
				replaced_faces += 1
			
			# patch begin
			elif len(words) == 1 and words[0] in rules:
				inside_patch = True
				
				patch_old = words[0]
				patch_new = rules.getNewShader(patch_old)
				patch_rule_rot_rad = math.radians(rules.getRotation(patch_old))
#				patch_rule_hscale = rules.getHScale(patch_old)
#				patch_rule_vscale = rules.getVScale(patch_old)
				
				new_line = patch_new
				
				replaced_patches += 1
			
			elif inside_patch:
				if   len(words) in (1, 7):
					new_line = line
					
					if words[0] in (")", "}"):
						inside_patch = False
				
				# patch column
				else:
					patch_column = words[1:-1]
					new_line = "( "
					
					# patch row
					while len(patch_column) > 0:
						patch_column.pop(0) # "("
						old_x = patch_column.pop(0)
						old_y = patch_column.pop(0)
						old_z = patch_column.pop(0)
						old_hshift = float(patch_column.pop(0))
						old_vshift = float(patch_column.pop(0))
						patch_column.pop(0) # ")"
						
						# TODO: scale + shift patch?
						
						new_hshift = math.cos(patch_rule_rot_rad)**2 * old_hshift \
						           + math.sin(patch_rule_rot_rad)**2 * old_vshift
						new_vshift = math.cos(patch_rule_rot_rad)**2 * old_vshift \
						           + math.sin(patch_rule_rot_rad)**2 * old_hshift
						
						new_line += "( " \
						         +        old_x \
						         +  " " + old_y \
						         +  " " + old_z \
						         +  " " + str(new_hshift) \
						         +  " " + str(new_vshift) \
						         +  " ) "
						
					new_line += ")"
			
			else:
				new_line = line
			
			new_content += new_line + "\n"
		
		return (new_content, replaced_faces, replaced_patches)


class Rules():
	def __init__(self, model):
		self.model = model
		
		self.rules = dict() # old shader -> (new shader, hscale, vscale, rot)
		
	def __contains__(self, rule):
		return rule in self.rules
		
	def __len__(self):
		return len(self.rules)
	
	def empty(self):
		return len(self) == 0
	
	def readFile(self, path):
		with open(path, "r") as f:
			content = f.read()
		
		self.clear()

		for line in content.splitlines():
			line = line.strip()

			if line.startswith("#") or line.startswith("//"):
				continue

			words = line.split()

			if len(words) != 5:
				continue

			(old, new, hscale, vscale, rot) = words
			
			try:
				hscale = float(hscale)
				vscale = float(vscale)
				rot = float(rot)
			except ValueError:
				continue
			
			self.__setRule(old, new, hscale, vscale, rot)
	
	def writeFile(self, path):
		out = "# This is a rules file for " + Static.TITLE + ".\n" \
		    + "# <old shader> <new shader> <horizontal scale> <vertical scale> <rotation>\n"
		
		for (old, (new, hscale, vscale, rot)) in self.rules.items():
			out += old + " " + new + " " + str(hscale) + " " + str(vscale) + " " + str(rot) + "\n"

		with open(path, "w") as f:
			f.write(out)
	
	def addRule(self, old, new):
		self.__setRule(old, new, None, None, None)
		self.setRotation(old)
		
	def __setRule(self, old, new, hscale, vscale, rot):
		self.rules[old] = [new, hscale, vscale, rot]
		
	def delRule(self, shader):
		if shader in self.rules:
			self.rules.pop(shader)
		
	def clear(self):
		self.rules.clear()
		
	def getNewShader(self, shader):
		if shader in self.rules:
			return self.rules[shader][0]
		else:
			return None
	
	def getHScale(self, shader):
		if shader in self.rules:
			return self.rules[shader][1]
		else:
			return None
		
	def getVScale(self, shader):
		if shader in self.rules:
			return self.rules[shader][2]
		else:
			return None
		
	def getRotation(self, shader):
		if shader in self.rules:
			return self.rules[shader][3]
		else:
			return None
		
	def setHScale(self, shader, value):
		if shader in self.rules:
			self.rules[shader][1] = value
			
	def setVScale(self, shader, value):
		if shader in self.rules:
			self.rules[shader][2] = value
			
	def setRotation(self, shader, value = None):
		if shader in self.rules:
			new_shader = self.getNewShader(shader)
			both_shaders_known = shader in self.model.shaders and new_shader in self.model.shaders
			
			if both_shaders_known:				
				old_width = self.model.shaders.getWidth(shader)
				old_height = self.model.shaders.getHeight(shader)
				
				new_width = self.model.shaders.getWidth(new_shader)
				new_height = self.model.shaders.getHeight(new_shader)				
			
				both_shaders_known = \
					old_width != 0 and old_height != 0 and new_width != 0 and new_height != 0
			
			if value == None:
				if both_shaders_known:
					if old_width > old_height and new_width < new_height \
					or old_width < old_height and new_width > new_height:
						rot = 90.0
					else:
						rot = 0.0
				else:
					rot = 0.0
			else:
				rot = value % 360.0
			
			if both_shaders_known:
				rot_rad = math.radians(rot)
				
				hscale = math.fabs(
					(old_width * math.cos(rot_rad) + old_height * math.sin(rot_rad)) / new_width
				)
				
				vscale = math.fabs(
					(old_height * math.cos(rot_rad) + old_width * math.sin(rot_rad)) / new_height				
				)
			else:
				hscale = 1.0
				vscale = 1.0
			
			self.rules[shader][1] = hscale
			self.rules[shader][2] = vscale
			self.rules[shader][3] = rot
			
			
class Model():
	def __init__(self):
		self.view = None
		
		self.shaders = Shaders()
		self.rules = Rules(self)
		self.map = Map(self)
		
	def openMap(self, path):
		"Opens and parses a map file."
		with open(path, "r") as f:
			self.map.parse(f.read())

		self.view.setStatus(os.path.basename(path) + " loaded.")

	def saveMap(self, path):
		"Builds the new map and saves it to a file."
		(new_content, replaced_faces, replaced_patches) = self.map.build(self.rules)
		
		with open(path, "w") as f:
			f.write(new_content)

		self.view.setStatus("Replaced " + str(replaced_faces) + " faces and " + str(replaced_patches) + " patches.")

	def openRules(self, path):
		"Opens and parses a rules file."
		self.rules.readFile(path)

		self.view.setStatus(str(len(self.rules)) + " rules loaded.")

	def saveRules(self, path):
		"Saves the current replacement rule set to a file."
		self.rules.writeFile(path)

		self.view.setStatus(str(len(self.rules)) + " rules saved.")
		
	def readCache(self):
		"Tries to read shader cache from filesystem."
		try:
			self.shaders.readCache(Static.SHADER_CACHE_FILE)
		except FileNotFoundError:
			return False
		except BaseException as e:
			print("Failed to read cache file " + Static.SHADER_CACHE_FILE + ": " + str(e), file = sys.stderr)
			return False
		else:
			self.view.setStatus("Loaded " + str(len(self.shaders)) + " shaders from cache.")
			return True
	
	def writeCache(self):
		"Saves shader cache to a file."
		try:
			self.shaders.writeCache(Static.SHADER_CACHE_FILE)
		except BaseException as e:
			print("Failed to write cache file " + Static.SHADER_CACHE_FILE + ": " + str(e), file = sys.stderr)
	
	def loadShaders(self, pd, basepath, homepath):
		"Loads shaders inside given pathes."
		changed = self.shaders.loadShaders(pd, basepath, homepath)
		
		if changed:
			self.writeCache()
		
			self.view.setStatus("Loaded " + str(len(self.shaders)) + " shaders from disk.")
		else:
			self.view.setStatus("Shader sources unchanged.")
		
	def reloadShaders(self, pd):
		"Reloads shaders."
		self.shaders.reloadShaders(pd)
		self.writeCache()
		
		self.view.setStatus("Loaded " + str(len(self.shaders)) + " shaders from disk.")
	

if __name__ == "__main__":
	app = QtGui.QApplication(sys.argv)

	model = Model()
	view = View(model)
	model.view = view
	
	view.restoreSession()
	
	if not model.readCache():
		view.askSettings()
	
	view.show()
	sys.exit(app.exec_())
