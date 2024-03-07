import asyncio
import logging
from typing import Optional
from pyht import Client, TTSOptions, Format, AsyncClient

import numpy as np


from aiohttp import ClientSession, ClientTimeout
from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import PlayHtSynthesizerConfig, PlayHtTurboSynthesizerConfig, SynthesizerType
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
)
from vocode.streaming.utils import convert_wav
from vocode.streaming.utils.mp3_helper import decode_mp3

TTS_ENDPOINT = "https://play.ht/api/v2/tts/stream"


class PlayHtTurboSynthesizer(BaseSynthesizer[PlayHtTurboSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: PlayHtTurboSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
        aiohttp_session: Optional[ClientSession] = None,
        max_backoff_retries=3,
        backoff_retry_delay=2,
    ):
        super().__init__(synthesizer_config, aiohttp_session)
        self.synthesizer_config = synthesizer_config
        self.api_key = synthesizer_config.api_key or getenv("PLAY_HT_API_KEY")
        self.user_id = synthesizer_config.user_id or getenv("PLAY_HT_USER_ID")
        if not self.api_key or not self.user_id:
            raise ValueError(
                "You must set the PLAY_HT_API_KEY and PLAY_HT_USER_ID environment variables"
            )
        playHTClient = Client(self.user_id, self.api_key)
        self.options = TTSOptions(
            # this voice id can be one of our prebuilt voices or your own voice clone id, refer to the`listVoices()` method for a list of supported voices.
            voice="s3://voice-cloning-zero-shot/d9ff78ba-d016-47f6-b0ef-dd630f59414e/female-cs/manifest.json",

            # you can pass any value between 8000 and 48000, 24000 is default
            sample_rate=self.synthesizer_config.sampling_rate,
        
            # the generated audio encoding, supports 'raw' | 'mp3' | 'wav' | 'ogg' | 'flac' | 'mulaw'
            format=Format.FORMAT_MP3,

            # playback rate of generated speech
            speed=1,
        )
        self.playHTClient = playHTClient
        self.words_per_minute = 150
        self.experimental_streaming = synthesizer_config.experimental_streaming
        self.max_backoff_retries = max_backoff_retries
        self.backoff_retry_delay = backoff_retry_delay



    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
       
        print("in create speech!!!!!")
      
        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.PLAY_HT_TURBO.value.split('_', 1)[-1]}.create_total",
        )
        # buff_size = 10485760
        # ptr = 0
        # buffer = np.empty(buff_size, np.float16)
        # buffer2=[]

        # return SynthesisResult(
        #             self.experimental_mp3_streaming_output_generator(
        #                 self.playHTClient.tts(text=message.text, voice_engine="PlayHT2.0-turbo", options=self.options), chunk_size, create_speech_span
        #             ),
                    
        #             lambda seconds: self.get_message_cutoff_from_voice_speed(
        #                 message, seconds, self.words_per_minute
        #             ),
        #         )
          # tracks the mp3 so far
        current_mp3_buffer = bytearray()
        # tracks the wav so far
        current_wav_buffer = bytearray()
        # the leftover chunks of the wav that haven't been sent to the output queue yet
        current_wav_output_buffer = bytearray()
        create_speech_span.end()
        convert_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.PLAY_HT_TURBO.value.split('_', 1)[-1]}.convert",
        )
        for i, chunk in enumerate(self.playHTClient.tts(text=message.text, voice_engine="PlayHT2.0-turbo", options=self.options)):
        # Do whatever you want with the stream, you could save it to a file, stream it in realtime to the browser or app, or to a telephony system
            # read_response = await response.read()
            # if i > 5:
            #     # for sample in np.frombuffer(chunk, np.float16):
            #     buffer2[ptr] = chunk
                # ptr += 1
            #  buffer[ptr] = np.frombuffer(chunk, np.float16)
            #  ptr += 1
            # for sample in np.frombuffer(chunk, np.float16):
            #     buffer[ptr] = sample
            #     ptr += 1
            if i > 0:
   
                # print("TTS RESPONSE")
                # print(type(chunk))
                # output_bytes_io = decode_mp3(chunk)

                current_mp3_buffer.extend(chunk)
        output_bytes = decode_mp3(bytes(current_mp3_buffer))


        # converted_output_bytes = convert_wav(
        # output_bytes,
        # output_sample_rate=self.synthesizer_config.sampling_rate,
        # output_encoding=self.synthesizer_config.audio_encoding,
        # )
        # # take the difference between the current_wav_buffer and the converted_output_bytes
        # # and put the difference in the output buffer
        # new_bytes = converted_output_bytes[len(current_wav_buffer) :]
        # current_wav_output_buffer.extend(new_bytes)

        result = self.create_synthesis_result_from_wav(
            synthesizer_config=self.synthesizer_config,
            file=output_bytes,
            message=message,
            chunk_size=chunk_size,
        )
        convert_span.end()
        print("CLOSING CLIENT")
        self.playHTClient.close()
        return result


        # backoff_retry_delay = self.backoff_retry_delay
        # max_backoff_retries = self.max_backoff_retries

        # for attempt in range(max_backoff_retries):
        #     response = await self.aiohttp_session.post(
        #         TTS_ENDPOINT,
        #         headers=headers,
        #         json=body,
        #         timeout=ClientTimeout(total=15),
        #     )

        #     if response.status == 429 and attempt < max_backoff_retries - 1:
        #         await asyncio.sleep(backoff_retry_delay)
        #         backoff_retry_delay *= 2  # Exponentially increase delay
        #         continue

        #     if not response.ok:
        #         raise Exception(f"Play.ht API error status code {response.status}")

        #     if self.experimental_streaming:
        #         return SynthesisResult(
        #             self.experimental_mp3_streaming_output_generator(
        #                 response, chunk_size, create_speech_span
        #             ),
        #             lambda seconds: self.get_message_cutoff_from_voice_speed(
        #                 message, seconds, self.words_per_minute
        #             ),
        #         )
        #     else:
        #         read_response = await response.read()
        #         create_speech_span.end()
        #         convert_span = tracer.start_span(
        #             f"synthesizer.{SynthesizerType.PLAY_HT.value.split('_', 1)[-1]}.convert",
        #         )
        #         output_bytes_io = decode_mp3(read_response)

        #         result = self.create_synthesis_result_from_wav(
        #             synthesizer_config=self.synthesizer_config,
        #             file=output_bytes_io,
        #             message=message,
        #             chunk_size=chunk_size,
        #         )
        #         convert_span.end()
        #         return result

        # raise Exception("Max retries reached for Play.ht API")

    async def create_speech_OLD(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        headers = {
            "AUTHORIZATION": f"Bearer {self.api_key}",
            "X-USER-ID": self.user_id,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        body = {
            "quality": "draft",
            "voice": self.synthesizer_config.voice_id,
            "text": message.text,
            "sample_rate": self.synthesizer_config.sampling_rate,
            "voice_engine": "PlayHT2.0-turbo"
        }
        if self.synthesizer_config.speed:
            body["speed"] = self.synthesizer_config.speed
        if self.synthesizer_config.seed:
            body["seed"] = self.synthesizer_config.seed
        if self.synthesizer_config.temperature:
            body["temperature"] = self.synthesizer_config.temperature

        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.PLAY_HT.value.split('_', 1)[-1]}.create_total",
        )

        backoff_retry_delay = self.backoff_retry_delay
        max_backoff_retries = self.max_backoff_retries

        for attempt in range(max_backoff_retries):
            response = await self.aiohttp_session.post(
                TTS_ENDPOINT,
                headers=headers,
                json=body,
                timeout=ClientTimeout(total=15),
            )

            if response.status == 429 and attempt < max_backoff_retries - 1:
                await asyncio.sleep(backoff_retry_delay)
                backoff_retry_delay *= 2  # Exponentially increase delay
                continue

            if not response.ok:
                raise Exception(f"Play.ht API error status code {response.status}")

            if self.experimental_streaming:
                return SynthesisResult(
                    self.experimental_mp3_streaming_output_generator(
                        response, chunk_size, create_speech_span
                    ),
                    lambda seconds: self.get_message_cutoff_from_voice_speed(
                        message, seconds, self.words_per_minute
                    ),
                )
            else:
                read_response = await response.read()
                create_speech_span.end()
                convert_span = tracer.start_span(
                    f"synthesizer.{SynthesizerType.PLAY_HT.value.split('_', 1)[-1]}.convert",
                )
                output_bytes_io = decode_mp3(read_response)

                result = self.create_synthesis_result_from_wav(
                    synthesizer_config=self.synthesizer_config,
                    file=output_bytes_io,
                    message=message,
                    chunk_size=chunk_size,
                )
                convert_span.end()
                return result

        raise Exception("Max retries reached for Play.ht API")
