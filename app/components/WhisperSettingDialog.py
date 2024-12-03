import os
from pathlib import Path
import subprocess
import hashlib
import sys

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QProgressBar,
                           QMessageBox, QLabel)
from qfluentwidgets import (ComboBoxSettingCard, MessageBoxBase, 
                          BodyLabel, PushButton, InfoBar, InfoBarPosition,
                          ProgressBar, ComboBox, HyperlinkButton)
from qfluentwidgets import FluentIcon as FIF

from ..common.config import cfg
from ..core.entities import WhisperModelEnum, TranscribeLanguageEnum
from ..config import MODEL_PATH
from ..core.utils.logger import setup_logger
from ..core.thread.download_thread import DownloadThread

logger = setup_logger("whisper_download")

# 使用阿里云镜像定义模型配置
# https://www.modelscope.cn/models/cjc1887415157/whisper.cpp/resolve/master/ggml-tiny.bin
# "mirrorLink": "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin?download=true"

# 使用阿里云镜像定义模型配置
WHISPER_MODELS = [
    {
        "label": "Tiny",
        "value": "ggml-tiny.bin", 
        "size": "77.7 MB",
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
        "mirrorLink": "https://www.modelscope.cn/models/cjc1887415157/whisper.cpp/resolve/master/ggml-tiny.bin",
        "sha": "bd577a113a864445d4c299885e0cb97d4ba92b5f"
    },
    {
        "label": "Base",
        "value": "ggml-base.bin",
        "size": "148 MB", 
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
        "mirrorLink": "https://www.modelscope.cn/models/cjc1887415157/whisper.cpp/resolve/master/ggml-base.bin",
        "sha": "465707469ff3a37a2b9b8d8f89f2f99de7299dac"
    },
    {
        "label": "Small",
        "value": "ggml-small.bin",
        "size": "488 MB",
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
        "mirrorLink": "https://www.modelscope.cn/models/cjc1887415157/whisper.cpp/resolve/master/ggml-small.bin",
        "sha": "55356645c2b361a969dfd0ef2c5a50d530afd8d5"
    },
    {
        "label": "Medium", 
        "value": "ggml-medium.bin",
        "size": "1.53 GB",
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
        "mirrorLink": "https://www.modelscope.cn/models/cjc1887415157/whisper.cpp/resolve/master/ggml-medium.bin",
        "sha": "fd9727b6e1217c2f614f9b698455c4ffd82463b4"
    },
    {
        "label": "large-v1",
        "value": "ggml-large-v1.bin",
        "size": "3.09 GB",
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v1.bin",
        "mirrorLink": "https://www.modelscope.cn/models/cjc1887415157/whisper.cpp/resolve/master/ggml-large-v1.bin",
        "sha": "b1caaf735c4cc1429223d5a74f0f4d0b9b59a299"
    },
    {
        "label": "large-v2",
        "value": "ggml-large-v2.bin", 
        "size": "3.09 GB",
        "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v2.bin",
        "mirrorLink": "https://www.modelscope.cn/models/cjc1887415157/whisper.cpp/resolve/master/ggml-large-v2.bin",
        "sha": "0f4c8e34f21cf1a914c59d8b3ce882345ad349d6"
    },
    # {
    #     "label": "Large(v3)",
    #     "value": "ggml-large-v3.bin",
    #     "size": "3.09 GB",
    #     "downloadLink": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
    #     "mirrorLink": "https://www.modelscope.cn/models/cjc1887415157/whisper.cpp/resolve/master/ggml-large-v3.bin",
    #     "sha": "ad82bf6a9043ceed055076d0fd39f5f186ff8062"
    # },
    # {
    #     "label": "Distil Large(v3)",
    #     "value": "ggml-distil-large-v3.bin",
    #     "size": "1.52 GB",
    #     "downloadLink": "https://huggingface.co/distil-whisper/distil-large-v3-ggml/resolve/main/ggml-distil-large-v3.bin?download=true",
    #     "mirrorLink": "https://www.modelscope.cn/models/cjc1887415157/whisper.cpp/resolve/master/ggml-distil-large-v3.bin",
    #     "sha": "5e61e98bdcf3b9a78516c59bf7d1a10d64cae67a"
    # }
]


class DownloadDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setWindowTitle(self.tr('下载模型'))
        self.download_thread = None

    def setup_ui(self):
        self.titleLabel = BodyLabel(self.tr('下载模型'), self)
        
        # 添加模型选择下拉框
        self.model_combo = ComboBox(self)
        self.model_combo.setFixedWidth(300)
        for model in WHISPER_MODELS:
            # 检查模型是否已下载
            model_path = os.path.join(MODEL_PATH, model['value'])
            downloaded = "✓ " if os.path.exists(model_path) else " "
            self.model_combo.addItem(f"{downloaded}{model['label']} ({model['size']})")
        
        # 进度条
        self.progress_bar = ProgressBar()
        self.progress_bar.hide()
        
        # 进度标签
        self.progress_label = BodyLabel()
        self.progress_label.hide()
        
        # 下载按钮
        self.download_button = PushButton(self.tr('下载'), self)
        self.download_button.clicked.connect(self.start_download)
        
        # 添加到布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.model_combo)
        self.viewLayout.addWidget(self.progress_bar)
        self.viewLayout.addWidget(self.progress_label)
        self.viewLayout.addWidget(self.download_button)
        # 设置间距
        self.viewLayout.setSpacing(10)

        # 只显示取消按钮
        self.yesButton.hide()
        self.cancelButton.setText(self.tr('关闭'))
            
    def start_download(self):
        selected_index = self.model_combo.currentIndex()
        model = WHISPER_MODELS[selected_index]
        save_path = os.path.join(MODEL_PATH, model['value'])
        
        # 检查模型文件是否已存在
        if os.path.exists(save_path):
            InfoBar.warning(
                title=self.tr('提示'),
                content=self.tr('模型文件已存在,无需重复下载'),
                parent=self.window(),
                duration=3000
            )
            return
            
        self.progress_bar.show()
        self.progress_label.show()
        self.download_button.setEnabled(False)
        
        self.download_thread = DownloadThread(
            model['mirrorLink'],
            save_path
        )
        self.download_thread.progress.connect(self.update_progress)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.error.connect(self.download_error)
        self.download_thread.start()
        
    def update_progress(self, value, status_msg):
        self.progress_bar.setValue(int(value))
        self.progress_label.setText(status_msg)
        
    def download_finished(self):
        InfoBar.success(
            title=self.tr('完成'),
            content=self.tr('模型下载完成!'),
            parent=self.window(),
            duration=3000
        )
        self.download_button.setEnabled(True)
        self.progress_label.setText(self.tr('下载完成'))
        
    def download_error(self, error):
        InfoBar.error(
            title=self.tr('下载错误'),
            content=error,
            parent=self.window(),
            duration=5000
        )
        self.download_button.setEnabled(True)
        self.progress_label.hide()

    def reject(self):
        if self.download_thread and self.download_thread.isRunning():
            logger.info("关闭下载对话框,终止下载")
            self.download_thread.stop()
        super().reject()

class WhisperSettingDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = BodyLabel(self.tr('Whisper 设置'), self)
        
        # 创建设置卡片
        self.model_card = ComboBoxSettingCard(
            cfg.whisper_model,
            FIF.ROBOT,
            self.tr('模型'),
            self.tr('选择Whisper模型'),
            [model.value for model in WhisperModelEnum],
            self
        )

        # 检查未下载的模型并从下拉框中移除
        for i in range(self.model_card.comboBox.count() - 1, -1, -1):
            model_text = self.model_card.comboBox.itemText(i).lower()
            model_config = next(
                (model for model in WHISPER_MODELS if model['label'].lower() == model_text),
                None
            )
            model_path = MODEL_PATH / model_config['value'] if model_config else None
            if model_config and model_path.exists():
                continue
            self.model_card.comboBox.removeItem(i)

        self.language_card = ComboBoxSettingCard(
            cfg.transcribe_language,
            FIF.LANGUAGE,
            self.tr('源语言'),
            self.tr('音频的源语言'), 
            [language.value for language in TranscribeLanguageEnum],
            self
        )
        self.language_card.comboBox.setMaxVisibleItems(6)

        self.buttonLayout = QHBoxLayout()
        # 创建下载模型按钮
        self.downloadButton = PushButton(self.tr('下载模型'), self)
        self.downloadButton.clicked.connect(self.show_download_dialog)
        
        self.openFolderButton = HyperlinkButton(
            '',
            self.tr('打开模型文件夹'), 
            self
        )
        self.openFolderButton.clicked.connect(self.open_folder)
        self.buttonLayout.addWidget(self.downloadButton)
        self.buttonLayout.addStretch()
        self.buttonLayout.addWidget(self.openFolderButton)

        # 添加到布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.model_card)
        self.viewLayout.addWidget(self.language_card)
        self.viewLayout.addLayout(self.buttonLayout)

        # 设置按钮文本
        self.yesButton.setText(self.tr('确定'))
        self.yesButton.clicked.connect(self.__onYesButtonClicked)
        self.widget.setMinimumWidth(400)


    def open_folder(self):
        if sys.platform == "win32":
            os.startfile(MODEL_PATH)
        elif sys.platform == "darwin":  # macOS
            subprocess.run(["open", MODEL_PATH])
        else:  # Linux
            subprocess.run(["xdg-open", MODEL_PATH])

    def show_download_dialog(self):
        download_dialog = DownloadDialog(self)
        download_dialog.show()

    def verify_sha(self, file_path, expected_sha):
        sha1 = hashlib.sha1()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha1.update(chunk)
        return sha1.hexdigest() == expected_sha

    def check_whisper_model(self):
        model_type = cfg.whisper_model.value.value
        model_files = list(Path(MODEL_PATH).glob(f"*ggml*{model_type}*.bin"))
        # 检测模型文件是否存在
        if not model_files:
            self.show_error_info(self.tr('模型文件不存在:') + model_type)
            logger.error(f"在 {MODEL_PATH} 目录下未找到包含 '{model_type}' 的模型文件")
            return False
            
        # 检测模型配置是否存在
        model_config = next((m for m in WHISPER_MODELS if model_type in m['value']), None)
        if not model_config:
            self.show_error_info(self.tr('模型配置不存在'))
            logger.error(f"未找到模型 '{model_type}' 的配置信息")
            return False
            
        # 验证模型文件的SHA值
        # model_file = model_files[0]  # 使用找到的第一个匹配文件
        # if not self.verify_sha(model_file, model_config['sha']):
        #     self.show_error_info(self.tr('模型文件SHA验证失败，请重新下载模型'))
        #     logger.error(f"模型文件 {model_file} 的SHA验证失败")
        #     return False
            
        return True
    
    def show_error_info(self, error_msg):
        InfoBar.error(
            title=self.tr('错误'),
            content=error_msg,
            parent=self.window(),
            duration=5000,
            position=InfoBarPosition.BOTTOM
        )

    def __onYesButtonClicked(self):
        if self.check_whisper_model():
            self.accept()
            InfoBar.success(
                self.tr("找到模型文件"),
                self.tr("Whisper设置已更新"),
                duration=3000,
                parent=self.window(),
                position=InfoBarPosition.BOTTOM
            )
            return
        if cfg.transcribe_language.value == TranscribeLanguageEnum.JAPANESE:
            InfoBar.warning(
                self.tr("请注意身体！！"),
                self.tr("小心肝儿,注意身体哦~"),
                duration=2000,
                parent=self.window(),
                position=InfoBarPosition.BOTTOM
            )