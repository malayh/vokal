import React from 'react';
import ReactDOM from 'react-dom';
import TextField from '@material-ui/core/TextField';
import Grid from '@material-ui/core/Grid';
import { Button } from '@material-ui/core';
import Avatar from '@material-ui/core/Avatar';

import {ActiveConnection} from './signaling';

import './styles.css';


class Room extends React.Component {
  render(){
    return (
      <div className="room-main">
        <span style={{display:"flex", justifyContent:"space-between"}}>
            <h3>Room # <em>1234</em> </h3>
            <Button variant="outlined" color="secondary" style={{padding:"0.2em"}}>Leave</Button>
        </span>
        <hr/>

        <div className="members">
          <span style={{display:"flex"}}>
            <Avatar style={{margin:"0.5em"}}>MH</Avatar>
            <span style={{margin:"1em"}}>Malay Hazarika</span>
          </span>

          <span style={{display:"flex"}}>
            <Avatar style={{margin:"0.5em"}}>MH</Avatar>
            <span style={{margin:"1em"}}>Malay Hazarika</span>
          </span>
        </div>
      </div>
    );
  }
}

class JoinCreate extends React.Component {

  constructor(props){
      super(props);

      this.state =  {
        name : "",
        room_id : "",

        room_id_helper_txt : null,
        name_helper_txt : null,

      }

      this.onJoin = this.onJoin.bind(this);
      this.onCreate = this.onCreate.bind(this);
      
      this.activeConnection = null;

      this.audio = React.createRef();
      this.onTrack = this.onTrack.bind(this)
  }

  onTrack(stream){
    this.audio.current.srcObject = stream;
  }
  async onJoin(e){
      if(this.state.name === ""){
        this.setState({name_helper_txt:"Must provide your name"});
        return;
      }
      this.setState({name_helper_txt:null});

      if(this.state.room_id === ""){
        this.setState({room_id_helper_txt:"Must provide room id to join"});
        return;
      }
      this.setState({room_id_helper_txt:null});

      try{
        this.activeConnection = new ActiveConnection(this.state.room_id,this.state.name,this.onTrack );
      } catch(e) {
        console.log(e);
      }
  }


  async onCreate(e){
    if(this.state.name === ""){
      this.setState({name_helper_txt:"Must provide your name"});
      return;
    }
    this.setState({name_helper_txt:null});
  }

  render(){
    return(
      <>
      <h1 id="logo-heading">Vokal</h1>
      <div>
        <TextField helperText={this.state.name_helper_txt} label="Your Name" onChange={(e=>this.setState({name:e.target.value}))} />
      </div>
      <div>
        <TextField helperText={this.state.room_id_helper_txt} label="Room ID" onChange={(e=>this.setState({room_id:e.target.value}))}/>
      </div>
      <div style={{marginTop:"1em", marginBottom:"3em"}}>
        <Button variant="contained" color="primary" style={{margin:"1em", marginLeft:0}} onClick={this.onJoin}>Join room</Button>
        <Button variant="contained" color="default"  onClick={this.onCreate}>Create room</Button>
      </div>
      <audio ref={this.audio} autoPlay></audio>
      </>
    );
  }
}


class VokalHome extends React.Component {
  constructor(props){
    super(props);
    this.state = {
      inARoom : false
    }

    this.audio = React.createRef();
  }
  render(){
    return (
        <Grid container spacing={2} justify='center' style={{padding:"5vw"}}>
            <Grid item lg={6} md={12} xs={12}>
              {this.state.inARoom ? <Room/>: <JoinCreate/> }
            </Grid>
        </Grid>
    );
  }
}

ReactDOM.render(
  <React.StrictMode>
    <>
    <VokalHome/>
    </>
  </React.StrictMode>,
  document.getElementById('root')
);

