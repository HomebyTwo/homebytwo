module CheckpointsTests exposing (..)

import Checkpoints exposing (..)
import Expect exposing (Expectation)
import Fuzz exposing (Fuzzer, int, list, string)
import Json.Decode as Decode exposing (decodeValue)
import Json.Encode as Encode
import Set exposing (Set)
import Test exposing (..)


placeDecoderTest : Test
placeDecoderTest =
    test "place json is properly decoded" <|
        \_ ->
            [ ( "altitude", Encode.float 1000.0 )
            , ( "coords" ,
                    [ ( "lat", Encode.float 46.5 )
                    , ( "lng", Encode.float 6.1 )
                    ] |> Encode.object
              )
            , ( "distance", Encode.float 1000.0 )
            , ( "elevation_gain", Encode.float 1000.0 )
            , ( "elevation_loss", Encode.float 1000.0 )
            , ( "name", Encode.string "test_name" )
            , ( "place_type", Encode.string "PPL" )
            , ( "schedule", Encode.string "1h" )
            ]
                |> Encode.object
                |> decodeValue Checkpoints.placeDecoder
                |> Result.map .distance
                |> Expect.equal (Ok 1000.0)


selectionFromCheckpointsTests : Test
selectionFromCheckpointsTests =
    describe "decoded checkpoints are transformed to selections"
        [ testSelectionFromCheckpoints "empty list" [] Set.empty
        , testSelectionFromCheckpoints "one checkpoint saved"
            [ { place = testPlace, fieldValue = "test_id", saved = True } ]
            (Set.fromList [ "test_id" ])
        , testSelectionFromCheckpoints "one checkpoint not saved"
            [ { place = testPlace, fieldValue = "test_id", saved = False } ]
            Set.empty
        , testSelectionFromCheckpoints "duplicate checkpoint"
            [ { place = testPlace, fieldValue = "test_id", saved = True }
            , { place = testPlace, fieldValue = "test_id", saved = True }
            ]
            (Set.fromList [ "test_id" ])
        ]


testSelectionFromCheckpoints : String -> List CheckpointPlace -> Set String -> Test
testSelectionFromCheckpoints description checkpoints result =
    test description <|
        \_ ->
            checkpoints
                |> selectionFromSavedCheckpoints
                |> Expect.equal result


testPlace =
    { name = "test_name"
    , placeType = "PPL"
    , altitude = 1000.0
    , schedule = "1h"
    , distance = 1000.0
    , elevationGain = 1000.0
    , elevationLoss = 1000.0
    , coords = { lat = 46.5, lng = 6.1 }
    }
