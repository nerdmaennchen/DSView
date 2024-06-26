##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019 Ben Dooks <ben.dooks@codethink.co.uk>
## Copyright (C) 2024 DreamSourceLab <support@dreamsourcelab.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

#
# 2024/3/18 DreamSourceLab : fix channel display error
# 2024/4/26 DreamSourceLab : add new option sampling edge
#

import sigrokdecode as srd

MAX_CHANNELS = 8

class Decoder(srd.Decoder):
    api_version = 3
    id = 'tdm_audio'
    name = 'TDM audio'
    longname = 'Time division multiplex audio'
    desc = 'TDM multi-channel audio protocol.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Audio']
    channels = (
        { 'id': 'clock', 'name': 'Bitclk', 'desc': 'Data bit clock', 'idn':'dec_tdm_audio_chan_clock' },
        { 'id': 'frame', 'name': 'Framesync', 'desc': 'Frame sync', 'idn':'dec_tdm_audio_chan_frame' },
        { 'id': 'data', 'name': 'Data', 'desc': 'Serial data', 'idn':'dec_tdm_audio_chan_data' },
    )
    options = (
        {'id': 'bps', 'desc': 'Bits per sample', 'default': 16, 'idn':'dec_tdm_audio_opt_bps' },
        {'id': 'channels', 'desc': 'Channels per frame', 'default': MAX_CHANNELS,
            'values': tuple(range(1, MAX_CHANNELS + 1)), 'idn':'dec_tdm_audio_opt_channels' },
        {'id': 'edge', 'desc': 'Clock edge to sample on', 'default': 'rising', 'values': ('rising', 'falling') , 'idn':'dec_tdm_audio_opt_edge'},
        {'id': 'sampling edge', 'desc': 'Sampling Edge', 'default': 'first edge', 'values': ('first edge', 'second edge'), 'idn':'dec_tdm_audio_opt_sampling_edge'},
    )
    annotations = tuple(('ch%d' % i, 'Ch%d' % i) for i in range(MAX_CHANNELS))
    annotation_rows = tuple(('ch%d-vals' % i, 'Ch%d' % i, (i,)) for i in range(MAX_CHANNELS))

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.channels = MAX_CHANNELS
        self.channel = 0
        self.bitdepth = 16
        self.bitcount = 0
        self.samplecount = 0
        self.lastsync = 0
        self.lastframe = 0
        self.data = 0
        self.ss_block = None

    def metdatadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.bitdepth = self.options['bps']
        self.edge = self.options['edge']

    def decode(self):
        while True:
            # Wait for edge of clock (sample on rising/falling edge).
            clock, frame, data = self.wait({0: self.edge[0]})

            self.data = (self.data << 1) | data
            self.bitcount += 1

            if self.ss_block is not None:
                if self.bitcount >= self.bitdepth:
                    self.bitcount = 0

                    c1 = 'Channel %d' % (self.channel % self.channels)
                    c2 = 'C%d' % (self.channel % self.channels)
                    c3 = '%d' % (self.channel % self.channels)
                    if self.bitdepth <= 8:
                        v = '%02x' % self.data
                    elif self.bitdepth <= 16:
                        v = '%04x' % self.data
                    else:
                        v = '%08x' % self.data
                    
                    ch = self.channel % self.channels

                    self.put(self.ss_block, self.samplenum, self.out_ann,
                             [ch, ['%s: %s' % (c1, v), '%s: %s' % (c2, v),
                                   '%s: %s' % (c3, v)]])

                    self.data = 0
                    self.ss_block = self.samplenum
                    self.samplecount += 1
                    self.channel += 1

            # Check for new frame.
            # Note, frame may be a single clock, or active for the first
            # sample in the frame.
            
            if frame != self.lastframe and frame == 1:
                self.channel = 0
                if self.options['sampling edge'] == 'first edge':
                    self.bitcount = 1
                    self.data = data
                else:
                    self.bitcount = 0
                    self.data = 0
                if self.ss_block is None:
                    self.ss_block = self.samplenum
                    
            self.lastframe = frame
