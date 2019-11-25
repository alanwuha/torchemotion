import os
import torch
import torchaudio
import pandas as pd
import numpy as np
import torch.nn.functional as F

class IemocapDataset(object):
    """
        Create a Dataset for Iemocap. Each item is a tuple of the form:
        (waveform, sample_rate, emotion, activation, valence, dominance)
    """

    _ext_audio = '.wav'
    _emotions = { 'ang': 1, 'hap': 2, 'exc': 3, 'sad': 4, 'fru': 5, 'fea': 6, 'sur': 7, 'neu': 8, 'xxx': 9 }

    def __init__(self, root='IEMOCAP_full_release'):
        """
        Args:
            root (string): Directory containing the Session folders
        """
        self.root = root

        # Iterate through all 5 sessions
        data = []
        for i in range(1, 6):
            # Define path to evaluation files of this session
            path = os.path.join(root, 'Session' + str(i), 'dialog', 'EmoEvaluation')

            # Get list of evaluation files
            files = [file for file in os.listdir(path) if file.endswith('.txt')]

            # Iterate through evaluation files to get utterance-level data
            for file in files:
                # Open file
                f = open(os.path.join(path, file), 'r')

                # Get list of lines containing utterance-level data. Trim and split each line into individual string elements.
                data += [line.strip()
                             .replace('[', '')
                             .replace(']', '')
                             .replace(' - ', '\t')
                             .replace(', ', '\t')
                             .split('\t')
                         for line in f if line.startswith('[')]

        # Create pandas dataframe
        self.df = pd.DataFrame(data, columns=['start', 'end', 'file', 'emotion', 'activation', 'valence', 'dominance'], dtype=np.float32)

        # Map emotion labels to numeric values
        self.df['emotion'] = self.df['emotion'].map(self._emotions).astype(np.float32)

        # Map file to correct path w.r.t to root
        self.df['file'] = [os.path.join('Session' + file[4], 'sentences', 'wav', file[:-5], file + self._ext_audio) for file in self.df['file']]

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()

        audio_name = os.path.join(self.root, self.df.loc[idx, 'file'])
        waveform, sample_rate = torchaudio.load(audio_name)
        emotion = self.df.loc[idx, 'emotion']
        activation = self.df.loc[idx, 'activation']
        valence = self.df.loc[idx, 'valence']
        dominance = self.df.loc[idx, 'dominance']

        sample = {
            'path': audio_name,
            'waveform': waveform,
            'sample_rate': sample_rate,
            'emotion': emotion,
            'activation': activation,
            'valence': valence,
            'dominance': dominance
        }

        return sample

    def collate_fn(batch):
        # Frame the signal into 20-40ms frames. 25ms is standard.
        # This means that the frame length for a 16kHz signal is 0.025 * 16000 = 400 samples.
        # Frame step is usually something like 10ms (160 samples), which allows some overlap to the frames.
        # The first 400 sample frame starts at sample 0, the next 400 sample frame starts at sample 160 etc until the end of the speech file is reached.
        # If the speech file does not divide into an even number, pad it with zeros so that it does.
        sample_rate = 16000
        n_channels = 1
        frame_length = np.int(0.025 * sample_rate)
        step_length = np.int(0.01 * sample_rate)

        frames = torch.zeros(0, n_channels, frame_length)
        for item in batch:
            waveform = item['waveform']
            original_waveform_length = waveform.shape[1]
            n_frames = np.int(np.ceil((original_waveform_length - frame_length) / step_length) + 1)
            padding_length = frame_length if original_waveform_length < frame_length else (frame_length + (n_frames - 1) * step_length - original_waveform_length)
            padded_waveform = F.pad(waveform, (0, padding_length))

            item_frames = torch.zeros(n_frames, n_channels, frame_length)
            for i in range(n_frames):
                item_frames[i] = padded_waveform[:, i*step_length:i*step_length+frame_length]
            frames = torch.cat((frames, item_frames), 0)

        return frames

# Example: Load Iemocap dataset
# iemocap_dataset = IemocapDataset('/home/alanwuha/Documents/Projects/datasets/iemocap/IEMOCAP_full_release')

# Example: Iterate through samples
# for i in range(len(iemocap_dataset)):
#     sample = iemocap_dataset[i]
#     print(i, sample)