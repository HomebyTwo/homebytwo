port module Checkpoints exposing (main)

-- Display route checkpoints
--
-- TODO: adapt possible checkpoints distance from route
-- TODO: filter/select checkpoints by placeType
-- TODO: use webcomponents instead of ports for Leaflet

import Browser
import Html exposing (..)
import Html.Attributes exposing (checked, class, classList, for, id, name, selected, type_, value, width)
import Html.Events exposing (onClick, onInput)
import Http exposing (Error)
import Json.Decode as Decode exposing (Decoder)
import Json.Decode.Pipeline exposing (custom, required)
import Json.Encode as Encode exposing (Value)
import Numeral exposing (format)
import SelectList exposing (Position(..), SelectList)
import Set exposing (Set)



-- MAIN


main =
    Browser.element
        { init = init
        , update = update
        , subscriptions = subscriptions
        , view = view
        }


init : Config -> ( Model, Cmd Msg )
init config =
    let
        url =
            config.displayUrl

        cmd =
            getSchedule url GotSchedule

        model =
            { config = config, status = LoadingSchedule }
    in
    ( model, cmd )


subscriptions : Model -> Sub Msg
subscriptions model =
    clickedPlace (clickedPlaceMessage model)


clickedPlaceMessage : Model -> { placeId : PlaceId, placeClass : String } -> Msg
clickedPlaceMessage model { placeId, placeClass } =
    case model.status of
        DisplaySchedule schedule ->
            case placeClass of
                "start" ->
                    PickedPlace (SelectList.selected schedule.start.data) placeId

                "finish" ->
                    PickedPlace (SelectList.selected schedule.finish.data) placeId

                "checkpoint" ->
                    ClickedCheckpoint placeId

                _ ->
                    Noop

        _ ->
            Noop



-- MODEL


type alias Model =
    { config : Config
    , status : Status
    }


type alias Config =
    { displayUrl : String
    , checkpointUrl : String
    , startUrl : String
    , finishUrl : String
    , csrfToken : String
    , canEdit : Bool
    }


type Status
    = Failure String
    | LoadingSchedule
    | DisplaySchedule Schedule


type alias Schedule =
    { checkpoints : CheckpointStatus
    , start : PlaceStatus
    , finish : PlaceStatus
    }


type alias CheckpointStatus =
    { status : EditStatus
    , data : ( List Checkpoint, CheckpointSelection )
    }


type alias PlaceStatus =
    { status : EditStatus
    , data : SelectList Place
    }


type EditStatus
    = Display
    | Loading
    | Editing
    | Saving


type alias CheckpointSelection =
    Set PlaceId


type Place
    = Start PlaceInfo
    | Finish PlaceInfo


type Checkpoint
    = Checkpoint PlaceInfo


type alias PlaceInfo =
    { name : String
    , placeType : String
    , altitude : Float
    , schedule : String
    , distance : Float
    , elevationGain : Float
    , elevationLoss : Float
    , coords : Coords
    , placeId : PlaceId
    }


type alias PlaceId =
    String


type alias Coords =
    { lat : Float, lng : Float }



-- PORTS


type alias PlacesMsg =
    { places : List PlaceMarker }


type alias PlaceMarker =
    { id : String
    , placeClass : String
    , name : String
    , placeType : String
    , schedule : String
    , coords : Coords
    , selected : Bool
    , edit : Bool
    }


port updatePlaces : PlacesMsg -> Cmd msg


port clickedPlace : ({ placeId : String, placeClass : String } -> msg) -> Sub msg


type Msg
    = Noop
      -- Initialize
    | ClickedRetry
    | GotSchedule (Result Http.Error ScheduleData)
      -- Checkpoints
    | ClickedEditCheckpoints
    | GotPossibleCheckpoints (Result Http.Error ( List Checkpoint, CheckpointSelection ))
    | ClickedCheckpoint String
    | ClickedSelectAllCheckpoints
    | ClickedClearAllCheckpoints
    | ClickedSaveCheckpoints
    | GotCheckpoints (Result Http.Error ( List Checkpoint, CheckpointSelection ))
      -- Start and Finish
    | ClickedEditPlace Place
    | GotPossiblePlace Place (Result Http.Error (SelectList Place))
    | PickedPlace Place String
    | ClickedSavePlace Place
    | GotPlace Place (Result Http.Error (SelectList Place))



-- UPDATE


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        Noop ->
            ( model, Cmd.none )

        ClickedRetry ->
            ( { model | status = LoadingSchedule }, getSchedule model.config.displayUrl GotSchedule )

        GotSchedule (Ok scheduleData) ->
            let
                schedule =
                    { checkpoints =
                        { status = Display
                        , data = scheduleData.checkpointData
                        }
                    , start =
                        { status = Display
                        , data = scheduleData.startData
                        }
                    , finish =
                        { status = Display
                        , data = scheduleData.finishData
                        }
                    }

                placeMarkers =
                    placeMarkersFromSchedule schedule

                updatePlacesCmd =
                    updatePlaces { places = placeMarkers }
            in
            ( { model | status = DisplaySchedule schedule }, updatePlacesCmd )

        GotSchedule (Err error) ->
            ( { model | status = Failure (errorToString error) }, Cmd.none )

        ClickedEditCheckpoints ->
            case model.status of
                DisplaySchedule schedule ->
                    let
                        updatedSchedule =
                            { schedule
                                | checkpoints =
                                    { status = Loading
                                    , data = schedule.checkpoints.data
                                    }
                            }
                    in
                    ( { model
                        | status = DisplaySchedule updatedSchedule
                      }
                    , getCheckpoints model.config.checkpointUrl
                    )

                _ ->
                    ( model, Cmd.none )

        GotPossibleCheckpoints (Ok data) ->
            case model.status of
                DisplaySchedule schedule ->
                    let
                        updatedSchedule =
                            { schedule | checkpoints = { status = Editing, data = data } }

                        status =
                            DisplaySchedule updatedSchedule

                        placeMarkers =
                            placeMarkersFromSchedule updatedSchedule
                    in
                    ( { model | status = status }
                    , updatePlaces <| PlacesMsg placeMarkers
                    )

                _ ->
                    ( model, Cmd.none )

        GotPossibleCheckpoints (Err error) ->
            ( { model | status = Failure (errorToString error) }, Cmd.none )

        ClickedCheckpoint placeId ->
            let
                updateSelectionFunction : List Checkpoint -> CheckpointSelection -> CheckpointSelection
                updateSelectionFunction _ selection =
                    if Set.member placeId selection then
                        Set.remove placeId selection

                    else
                        Set.insert placeId selection
            in
            updateCheckpointSelection updateSelectionFunction model

        ClickedSelectAllCheckpoints ->
            let
                updateSelectionFunction : List Checkpoint -> CheckpointSelection -> CheckpointSelection
                updateSelectionFunction checkpoints _ =
                    List.map placeInfoFromCheckpoint checkpoints
                        |> List.map .placeId
                        |> Set.fromList
            in
            updateCheckpointSelection updateSelectionFunction model

        ClickedClearAllCheckpoints ->
            let
                updateSelectionFunction : List Checkpoint -> CheckpointSelection -> CheckpointSelection
                updateSelectionFunction _ _ =
                    Set.empty
            in
            updateCheckpointSelection updateSelectionFunction model

        ClickedSaveCheckpoints ->
            case model.status of
                DisplaySchedule ({ checkpoints, start, finish } as schedule) ->
                    let
                        updatedCheckpoints =
                            { checkpoints | status = Saving }

                        updatedSchedule =
                            { schedule | checkpoints = updatedCheckpoints }

                        ( _, selection ) =
                            checkpoints.data
                    in
                    ( { model | status = DisplaySchedule updatedSchedule }
                    , postCheckpoints model.config.checkpointUrl model.config.csrfToken selection
                    )

                _ ->
                    ( model, Cmd.none )

        GotCheckpoints (Ok data) ->
            case model.status of
                DisplaySchedule ({ checkpoints, start, finish } as schedule) ->
                    let
                        updatedCheckpoints =
                            { status = Display, data = data }

                        updatedSchedule =
                            { schedule | checkpoints = updatedCheckpoints }

                        placeMarkers =
                            placeMarkersFromSchedule updatedSchedule
                    in
                    ( { model | status = DisplaySchedule updatedSchedule }
                    , updatePlaces <| PlacesMsg placeMarkers
                    )

                _ ->
                    ( model, Cmd.none )

        GotCheckpoints (Err error) ->
            ( { model | status = Failure (errorToString error) }, Cmd.none )

        ClickedEditPlace place ->
            case model.status of
                DisplaySchedule schedule ->
                    let
                        ( placeStatus, url ) =
                            case place of
                                Start _ ->
                                    ( schedule.start, model.config.startUrl )

                                Finish _ ->
                                    ( schedule.finish, model.config.finishUrl )

                        updatedPlaceStatus =
                            { placeStatus | status = Loading }

                        updatedSchedule =
                            case place of
                                Start _ ->
                                    { schedule | start = updatedPlaceStatus }

                                Finish _ ->
                                    { schedule | finish = updatedPlaceStatus }
                    in
                    ( { model | status = DisplaySchedule updatedSchedule }
                    , getPlace place url
                    )

                _ ->
                    ( model, Cmd.none )

        GotPossiblePlace place (Ok placeList) ->
            case model.status of
                DisplaySchedule schedule ->
                    let
                        updatedStatus =
                            { status = Editing, data = placeList }

                        updatedSchedule =
                            case place of
                                Start _ ->
                                    { schedule | start = updatedStatus }

                                Finish _ ->
                                    { schedule | finish = updatedStatus }

                        placeMarkers =
                            placeMarkersFromSchedule updatedSchedule
                    in
                    ( { model | status = DisplaySchedule updatedSchedule }
                    , updatePlaces <| PlacesMsg placeMarkers
                    )

                _ ->
                    ( model, Cmd.none )

        GotPossiblePlace _ (Err error) ->
            ( { model | status = Failure (errorToString error) }, Cmd.none )

        PickedPlace place index ->
            case model.status of
                DisplaySchedule schedule ->
                    let
                        old_place_list =
                            case place of
                                Start _ ->
                                    schedule.start.data

                                Finish _ ->
                                    schedule.finish.data

                        old_index =
                            SelectList.index old_place_list

                        new_index =
                            Maybe.withDefault old_index (String.toInt index)

                        data =
                            SelectList.selectedMap (\_ list -> list) old_place_list
                                |> List.drop new_index
                                |> List.head
                                |> Maybe.withDefault old_place_list

                        updatedStatus =
                            { status = Editing, data = data }

                        updatedSchedule =
                            case place of
                                Start _ ->
                                    { schedule | start = updatedStatus }

                                Finish _ ->
                                    { schedule | finish = updatedStatus }

                        placeMarkers =
                            placeMarkersFromSchedule updatedSchedule
                    in
                    ( { model | status = DisplaySchedule updatedSchedule }
                    , updatePlaces <| PlacesMsg placeMarkers
                    )

                _ ->
                    ( model, Cmd.none )

        ClickedSavePlace place ->
            case model.status of
                DisplaySchedule schedule ->
                    let
                        ( data, url ) =
                            case place of
                                Start _ ->
                                    ( schedule.start.data, model.config.startUrl )

                                Finish _ ->
                                    ( schedule.finish.data, model.config.finishUrl )

                        updatedStatus =
                            { data = data, status = Saving }

                        updatedSchedule =
                            case place of
                                Start _ ->
                                    { schedule | start = updatedStatus }

                                Finish _ ->
                                    { schedule | finish = updatedStatus }

                        placeId =
                            SelectList.selected data
                                |> placeInfoFromPlace
                                |> .placeId
                    in
                    ( { model | status = DisplaySchedule updatedSchedule }
                    , postPlace place url model.config.csrfToken placeId
                    )

                _ ->
                    ( model, Cmd.none )

        GotPlace place (Ok data) ->
            case model.status of
                DisplaySchedule schedule ->
                    let
                        updatedStatus =
                            { status = Display, data = data }

                        updatedSchedule =
                            case place of
                                Start _ ->
                                    { schedule | start = updatedStatus }

                                Finish _ ->
                                    { schedule | finish = updatedStatus }
                    in
                    ( { model | status = DisplaySchedule updatedSchedule }, Cmd.none )

                _ ->
                    ( model, Cmd.none )

        GotPlace _ (Err error) ->
            ( { model | status = Failure (errorToString error) }, Cmd.none )


updateCheckpointSelection : (List Checkpoint -> CheckpointSelection -> CheckpointSelection) -> Model -> ( Model, Cmd Msg )
updateCheckpointSelection updateSelectionFunction model =
    case model.status of
        DisplaySchedule schedule ->
            case schedule.checkpoints.status of
                Editing ->
                    let
                        ( checkpoints, selection ) =
                            schedule.checkpoints.data

                        updatedSelection =
                            updateSelectionFunction checkpoints selection

                        updatedSchedule =
                            { schedule
                                | checkpoints =
                                    { status = Editing
                                    , data = ( checkpoints, updatedSelection )
                                    }
                            }

                        placeMarkers =
                            placeMarkersFromSchedule updatedSchedule

                        updatePlacesCmd =
                            updatePlaces { places = placeMarkers }
                    in
                    ( { model | status = DisplaySchedule updatedSchedule }, updatePlacesCmd )

                _ ->
                    ( model, Cmd.none )

        _ ->
            ( model, Cmd.none )


isSelected : CheckpointSelection -> Checkpoint -> Bool
isSelected selection (Checkpoint checkpointInfo) =
    Set.member checkpointInfo.placeId selection


placeInfoFromCheckpoint : Checkpoint -> PlaceInfo
placeInfoFromCheckpoint (Checkpoint placeInfo) =
    placeInfo


placeInfoFromPlace : Place -> PlaceInfo
placeInfoFromPlace place =
    case place of
        Start placeInfo ->
            placeInfo

        Finish placeInfo ->
            placeInfo



-- Place Markers for Leaflet


placeMarkersFromSchedule : Schedule -> List PlaceMarker
placeMarkersFromSchedule { checkpoints, start, finish } =
    placeMarkersFromCheckpoints checkpoints
        ++ placeMarkersFromPlace start
        ++ placeMarkersFromPlace finish


placeMarkersFromCheckpoints : CheckpointStatus -> List PlaceMarker
placeMarkersFromCheckpoints { status, data } =
    let
        ( checkpoints, selection ) =
            data

        areSelected =
            List.map (isSelected selection) checkpoints
    in
    case status of
        Editing ->
            List.map2 (placeMarkerFromCheckpoint True) areSelected checkpoints

        _ ->
            List.map2 (placeMarkerFromCheckpoint False) areSelected checkpoints


placeMarkerFromCheckpoint : Bool -> Bool -> Checkpoint -> PlaceMarker
placeMarkerFromCheckpoint edit selected (Checkpoint checkpointInfo) =
    placeMarkerFromPlaceInfo "checkpoint" selected edit checkpointInfo.placeId checkpointInfo


placeMarkersFromPlace : PlaceStatus -> List PlaceMarker
placeMarkersFromPlace { status, data } =
    SelectList.selectedMap (placeMarkerMap status) data


placeMarkerMap : EditStatus -> Position -> SelectList Place -> PlaceMarker
placeMarkerMap status position selectList =
    let
        place =
            SelectList.selected selectList

        selected =
            position == Selected

        index =
            SelectList.index selectList

        edit =
            case status of
                Editing ->
                    True

                _ ->
                    False
    in
    case place of
        Start info ->
            placeMarkerFromPlaceInfo "start" selected edit (String.fromInt index) info

        Finish info ->
            placeMarkerFromPlaceInfo "finish" selected edit (String.fromInt index) info


placeMarkerFromPlaceInfo : String -> Bool -> Bool -> PlaceId -> PlaceInfo -> PlaceMarker
placeMarkerFromPlaceInfo placeClass selected edit placeId placeInfo =
    PlaceMarker
        placeId
        placeClass
        (placeNameText placeInfo.name placeInfo.altitude)
        placeInfo.placeType
        placeInfo.schedule
        placeInfo.coords
        selected
        edit



-- VIEW


view : Model -> Html Msg
view model =
    div [ class "checkpoints mrgv-" ] <|
        case model.status of
            LoadingSchedule ->
                [ text "Loading route schedule..." ]

            DisplaySchedule { start, checkpoints, finish } ->
                let
                    canEdit =
                        model.config.canEdit
                in
                [ div [ class "schedule" ]
                    [ viewPlace canEdit start
                    , viewCheckpoints checkpoints
                    , viewPlace canEdit finish
                    , viewCheckpointEditButton canEdit checkpoints.status
                    ]
                ]

            Failure error ->
                [ text error
                , button
                    [ class "btn btn--secondary btn--block"
                    , onClick ClickedRetry
                    ]
                    [ text (messageToButtonText ClickedRetry) ]
                ]



--  Checkpoints


viewCheckpoints : CheckpointStatus -> Html Msg
viewCheckpoints { status, data } =
    case status of
        Editing ->
            viewEditCheckpoints data

        _ ->
            viewDisplayCheckpoints data


viewDisplayCheckpoints : ( List Checkpoint, CheckpointSelection ) -> Html Msg
viewDisplayCheckpoints ( checkpoints, selection ) =
    case checkpoints of
        [] ->
            div [ class "box box--default box--tight mrgv- pdg- place" ]
                [ text "No checkpoint has been added to this route. With checkpoints, you can track your progress during your run." ]

        _ ->
            List.filter (isSelected selection) checkpoints
                |> List.map placeInfoFromCheckpoint
                |> List.map viewDisplayCheckpoint
                |> ul [ class "list list--stacked" ]


viewDisplayCheckpoint : PlaceInfo -> Html Msg
viewDisplayCheckpoint checkpointInfo =
    div [ class "box box--tight box--default mrgv- pdg- place" ]
        [ viewCheckpointInfo checkpointInfo ]


viewEditCheckpoints : ( List Checkpoint, CheckpointSelection ) -> Html Msg
viewEditCheckpoints ( checkpoints, selection ) =
    case checkpoints of
        [] ->
            div [ class "box box--default box--tight mrgv- pdg- place" ]
                [ text "Sorry, no checkpoint was found for this route. " ]

        _ ->
            div []
                [ viewClearSelectAllButtons
                , List.map placeInfoFromCheckpoint checkpoints
                    |> List.map (viewEditCheckpoint selection)
                    |> ul [ class "list list--stacked" ]
                ]


viewEditCheckpoint : CheckpointSelection -> PlaceInfo -> Html Msg
viewEditCheckpoint selection checkpointInfo =
    let
        isChecked =
            Set.member checkpointInfo.placeId selection
    in
    li
        [ class "box box--tight mrgv- place"
        , classList [ ( "box--default", isChecked ) ]
        ]
        [ label [ for checkpointInfo.placeId, class "label pdg0" ]
            [ table [ class "mrgv0 pdg0" ]
                [ tbody []
                    [ tr []
                        [ td [ class "text-center", width 10 ] [ viewCheckpointCheckbox isChecked checkpointInfo ]
                        , td [] [ viewCheckpointInfo checkpointInfo ]
                        ]
                    ]
                ]
            ]
        ]


viewCheckpointCheckbox : Bool -> PlaceInfo -> Html Msg
viewCheckpointCheckbox isChecked checkpointInfo =
    input
        [ id checkpointInfo.placeId
        , type_ "checkbox"
        , class "checkbox"
        , value checkpointInfo.placeId
        , checked isChecked
        , onClick (ClickedCheckpoint checkpointInfo.placeId)
        ]
        []


viewCheckpointInfo : PlaceInfo -> Html Msg
viewCheckpointInfo placeInfo =
    div [ class "grid grid--tight" ]
        [ viewCheckpointPlaceName placeInfo.name placeInfo.altitude
        , viewPlaceSchedule placeInfo.schedule
        , viewPlaceType placeInfo.placeType
        , viewPlaceElevationAndDistance placeInfo.distance placeInfo.elevationGain placeInfo.elevationLoss
        ]


viewCheckpointPlaceName : String -> Float -> Html Msg
viewCheckpointPlaceName name altitude =
    div
        [ class "w-2/3 sm-w-4/5 grid__item place__name" ]
        [ text (placeNameText name altitude)
        ]



-- Places


viewPlace : Bool -> PlaceStatus -> Html Msg
viewPlace canEdit { status, data } =
    let
        place =
            SelectList.selected data

        placeInfo =
            placeInfoFromPlace place

        title =
            case place of
                Start _ ->
                    "Start"

                Finish _ ->
                    "Finish"

        placeName =
            case status of
                Editing ->
                    div
                        [ class "w-2/3 sm-w-4/5 grid__item place__name" ]
                        [ div [ class "media media--small" ]
                            [ div [ class "media__body" ]
                                [ select
                                    [ class "field field--small", onInput (PickedPlace place) ]
                                    (SelectList.selectedMap selectOption data)
                                ]
                            , div [ class "media__right" ]
                                [ viewPlaceEditButton canEdit status place
                                ]
                            ]
                        ]

                _ ->
                    div
                        [ class "w-2/3 sm-w-4/5 grid__item place__name" ]
                        [ text (placeNameText placeInfo.name placeInfo.altitude)
                        , span [ class "pdgl" ]
                            [ viewPlaceEditButton canEdit status place
                            ]
                        ]
    in
    div
        [ class "box box--tight box--default mrgv- pdg- place" ]
        [ h3 [ class "mrgv0" ] [ text title ]
        , div [ class "grid grid--tight" ]
            [ placeName
            , viewPlaceSchedule placeInfo.schedule
            , viewPlaceType placeInfo.placeType
            , viewPlaceElevationAndDistance placeInfo.distance placeInfo.elevationGain placeInfo.elevationLoss
            ]
        ]


selectOption : SelectList.Position -> SelectList Place -> Html Msg
selectOption position placeList =
    let
        index =
            SelectList.index placeList |> String.fromInt

        isChecked =
            position == Selected

        placeInfo =
            placeInfoFromPlace <| SelectList.selected placeList
    in
    option
        [ value index, selected isChecked ]
        [ text (placeNameText placeInfo.name placeInfo.altitude) ]



-- PlaceInfo


placeNameText : String -> Float -> String
placeNameText name altitude =
    name ++ ", " ++ format "0,0" altitude ++ "m"


viewPlaceSchedule : String -> Html Msg
viewPlaceSchedule schedule =
    div
        [ class "w-1/3 sm-w-1/5 grid__item text-right" ]
        [ text schedule ]


viewPlaceType : String -> Html Msg
viewPlaceType placeType =
    div
        [ class "w-1/2 grid__item text-small text-left" ]
        [ text placeType ]


viewPlaceElevationAndDistance : Float -> Float -> Float -> Html Msg
viewPlaceElevationAndDistance distance elevationGain elevationLoss =
    div
        [ class "w-1/2 grid__item text-small text-right" ]
        [ text <| format "0,0.0" distance ++ "km"
        , text <| " ➚ " ++ format "0,0" elevationGain ++ "m"
        , text <| " ➘ " ++ format "0,0" elevationLoss ++ "m"
        ]



-- Buttons


viewPlaceEditButton : Bool -> EditStatus -> Place -> Html Msg
viewPlaceEditButton canEdit placeStatus place =
    if canEdit then
        case placeStatus of
            Display ->
                button [ class "btn btn--secondary btn--small", onClick (ClickedEditPlace place) ]
                    [ text "Edit" ]

            Loading ->
                div [ class "loader" ] []

            Editing ->
                button [ class "btn btn--primary btn--small", onClick (ClickedSavePlace place) ]
                    [ text "Save" ]

            Saving ->
                div [ class "loader" ] []

    else
        text ""


viewCheckpointEditButton : Bool -> EditStatus -> Html Msg
viewCheckpointEditButton canEdit checkpointStatus =
    if canEdit then
        case checkpointStatus of
            Display ->
                button
                    [ class "btn btn--primary btn--block"
                    , onClick ClickedEditCheckpoints
                    ]
                    [ text (messageToButtonText ClickedEditCheckpoints) ]

            Loading ->
                button
                    [ class "btn btn--primary btn--block btn--disabled"
                    ]
                    [ div [ class "inline-flex align-items-center" ]
                        [ div [ class "loader" ] []
                        , div [ class "pdgl--" ] [ text "Loading Checkpoints..." ]
                        ]
                    ]

            Editing ->
                button
                    [ class "btn btn--primary btn--block"
                    , onClick ClickedSaveCheckpoints
                    ]
                    [ text (messageToButtonText ClickedSaveCheckpoints) ]

            Saving ->
                button
                    [ class "btn btn--primary btn--block btn--disabled"
                    ]
                    [ div [ class "inline-flex align-items-center" ]
                        [ div [ class "loader" ] []
                        , div [ class "pdgl--" ] [ text "Saving Checkpoints..." ]
                        ]
                    ]

    else
        text ""


viewClearSelectAllButtons : Html Msg
viewClearSelectAllButtons =
    div []
        [ h4 [] [ text "Edit Checkpoints" ]
        , div [ class "mrgv-" ]
            [ button
                [ class "btn btn--primary btn--block btn--small"
                , onClick ClickedSaveCheckpoints
                ]
                [ text "Save Checkpoints" ]
            ]
        , div [ class "grid grid--small" ]
            [ div [ class "grid__item w-1/2" ]
                [ button
                    [ onClick ClickedSelectAllCheckpoints
                    , class "btn btn--secondary btn--block btn--small "
                    ]
                    [ text (messageToButtonText ClickedSelectAllCheckpoints) ]
                ]
            , div [ class "grid__item w-1/2" ]
                [ button
                    [ onClick ClickedClearAllCheckpoints
                    , class "btn btn--secondary btn--block btn--small "
                    ]
                    [ text (messageToButtonText ClickedClearAllCheckpoints) ]
                ]
            ]
        ]


messageToButtonText : Msg -> String
messageToButtonText message =
    case message of
        ClickedRetry ->
            "Retry"

        ClickedEditCheckpoints ->
            "Edit Checkpoints"

        ClickedSaveCheckpoints ->
            "Save Checkpoints"

        ClickedSelectAllCheckpoints ->
            "Select All"

        ClickedClearAllCheckpoints ->
            "Clear All"

        _ ->
            ""



-- JSON Decoders


type alias ScheduleData =
    { checkpointData : ( List Checkpoint, Set PlaceId )
    , startData : SelectList Place
    , finishData : SelectList Place
    }


scheduleDecoder : Decoder ScheduleData
scheduleDecoder =
    Decode.succeed ScheduleData
        |> custom checkpointDataDecoder
        |> custom startDataDecoder
        |> custom finishDataDecoder



-- Checkpoints Data


checkpointDataDecoder : Decoder ( List Checkpoint, Set PlaceId )
checkpointDataDecoder =
    Decode.map2 Tuple.pair
        checkpointsDecoder
        checkpointSelectionDecoder
        |> Decode.field "checkpoints"


checkpointSelectionDecoder : Decoder (Set PlaceId)
checkpointSelectionDecoder =
    Decode.map2 Tuple.pair
        (Decode.field "saved" Decode.bool)
        (Decode.field "place_id" Decode.string)
        |> Decode.list
        |> Decode.map filteredCheckpointSelection


filteredCheckpointSelection : List ( Bool, PlaceId ) -> Set PlaceId
filteredCheckpointSelection tupleList =
    List.filter Tuple.first tupleList
        |> List.map Tuple.second
        |> Set.fromList


checkpointsDecoder : Decoder (List Checkpoint)
checkpointsDecoder =
    placeJsonDecoder
        |> Decode.map placeInfoFromPlaceJson
        |> Decode.map Checkpoint
        |> Decode.list



-- Start


startDataDecoder : Decoder (SelectList Place)
startDataDecoder =
    placeJsonDecoder
        |> Decode.list
        |> Decode.andThen toSelectList
        |> Decode.map (SelectList.map Start)
        |> Decode.field "start"



-- Finish


finishDataDecoder : Decoder (SelectList Place)
finishDataDecoder =
    placeJsonDecoder
        |> Decode.list
        |> Decode.andThen toSelectList
        |> Decode.map (SelectList.map Finish)
        |> Decode.field "finish"



-- Place


toSelectList : List PlaceJson -> Decoder (SelectList PlaceInfo)
toSelectList placeJsonList =
    let
        savedTupleList =
            List.indexedMap Tuple.pair placeJsonList
                |> List.filter (\tuple -> Tuple.second tuple |> .saved)
    in
    case savedTupleList of
        ( savedIndex, savedPlace ) :: [] ->
            SelectList.fromLists
                (List.take savedIndex placeJsonList)
                savedPlace
                (List.drop (savedIndex + 1) placeJsonList)
                |> SelectList.map placeInfoFromPlaceJson
                |> Decode.succeed

        _ ->
            Decode.fail "List of places must contain exactly one saved place."


type alias PlaceJson =
    { name : String
    , placeType : String
    , altitude : Float
    , schedule : String
    , distance : Float
    , elevationGain : Float
    , elevationLoss : Float
    , coords : Coords
    , placeId : PlaceId
    , saved : Bool
    }


placeInfoFromPlaceJson : PlaceJson -> PlaceInfo
placeInfoFromPlaceJson placeJson =
    PlaceInfo
        placeJson.name
        placeJson.placeType
        placeJson.altitude
        placeJson.schedule
        placeJson.distance
        placeJson.elevationGain
        placeJson.elevationLoss
        placeJson.coords
        placeJson.placeId


placeJsonDecoder : Decoder PlaceJson
placeJsonDecoder =
    Decode.succeed PlaceJson
        |> required "name" Decode.string
        |> required "place_type" Decode.string
        |> required "altitude" Decode.float
        |> required "schedule" Decode.string
        |> required "distance" Decode.float
        |> required "elevation_gain" Decode.float
        |> required "elevation_loss" Decode.float
        |> required "coords" coordsDecoder
        |> required "place_id" Decode.string
        |> required "saved" Decode.bool


coordsDecoder : Decoder Coords
coordsDecoder =
    Decode.succeed Coords
        |> required "lat" Decode.float
        |> required "lng" Decode.float



-- JSON Encoders


checkpointSelectionEncoder : CheckpointSelection -> Value
checkpointSelectionEncoder selection =
    Encode.set Encode.string selection



-- HTTP


getSchedule : String -> (Result Error ScheduleData -> Msg) -> Cmd Msg
getSchedule url msg =
    Http.get
        { url = url
        , expect = Http.expectJson msg scheduleDecoder
        }


getCheckpoints : String -> Cmd Msg
getCheckpoints url =
    Http.get
        { url = url
        , expect = Http.expectJson GotPossibleCheckpoints checkpointDataDecoder
        }


postCheckpoints : String -> String -> CheckpointSelection -> Cmd Msg
postCheckpoints url csrfToken selection =
    let
        body =
            Encode.object [ ( "checkpoints", checkpointSelectionEncoder selection ) ]
    in
    Http.request
        { method = "POST"
        , headers = [ Http.header "X-CSRFToken" csrfToken ]
        , url = url
        , body = Http.jsonBody body
        , expect = Http.expectJson GotCheckpoints checkpointDataDecoder
        , timeout = Nothing
        , tracker = Nothing
        }


getPlace : Place -> String -> Cmd Msg
getPlace place url =
    let
        decoder =
            case place of
                Start _ ->
                    startDataDecoder

                Finish _ ->
                    finishDataDecoder
    in
    Http.get
        { url = url
        , expect = Http.expectJson (GotPossiblePlace place) decoder
        }


postPlace : Place -> String -> String -> PlaceId -> Cmd Msg
postPlace place url csrfToken placeId =
    let
        ( body, decoder ) =
            case place of
                Start _ ->
                    ( Encode.object [ ( "start", Encode.string placeId ) ], startDataDecoder )

                Finish _ ->
                    ( Encode.object [ ( "finish", Encode.string placeId ) ], finishDataDecoder )
    in
    Http.request
        { method = "POST"
        , headers = [ Http.header "X-CSRFToken" csrfToken ]
        , url = url
        , body = Http.jsonBody body
        , expect = Http.expectJson (GotPlace place) decoder
        , timeout = Nothing
        , tracker = Nothing
        }


errorToString : Http.Error -> String
errorToString error =
    case error of
        Http.BadUrl url ->
            "The URL " ++ url ++ " was invalid"

        Http.Timeout ->
            "Unable to reach the server, try again"

        Http.NetworkError ->
            "Unable to reach the server, check your network connection"

        Http.BadStatus 500 ->
            "The server had a problem, try again later."

        Http.BadStatus 400 ->
            "Verify your information and try again"

        Http.BadStatus _ ->
            "Unknown error"

        Http.BadBody errorMessage ->
            errorMessage
